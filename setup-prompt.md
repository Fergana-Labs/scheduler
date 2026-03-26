# Scheduled — Self-Hosted Setup

You are setting up Scheduled, an AI scheduling assistant that lives in Gmail. It reads incoming scheduling emails, checks the user's calendar, and drafts replies with proposed meeting times.

This setup will deploy everything to the user's Google Cloud Platform project. Follow each step carefully. Do not skip steps. If a step fails, diagnose the error before continuing.

---

## Phase 1: Prerequisites

### 1.1 Install gcloud CLI

```bash
which gcloud || brew install google-cloud-sdk
```

If `brew` is not available, follow https://cloud.google.com/sdk/docs/install

### 1.2 Authenticate

```bash
gcloud auth login
```

This opens a browser. The user clicks "Allow" to authenticate their Google account.

Then set the application default credentials (needed for Firestore and Vertex AI):

```bash
gcloud auth application-default login
```

### 1.3 Get the user's email

```bash
ACCOUNT_EMAIL=$(gcloud config get-value account)
echo "Setting up Scheduled for: $ACCOUNT_EMAIL"
```

---

## Phase 2: GCP Project

### 2.1 Create project

```bash
PROJECT_ID="scheduled-$(openssl rand -hex 4)"
gcloud projects create $PROJECT_ID --name="Scheduled"
gcloud config set project $PROJECT_ID
echo "Created project: $PROJECT_ID"
```

### 2.2 Link billing

Link to Fergana Labs' billing account so the user doesn't need to enter a credit card:

```bash
# Use Fergana Labs billing account
BILLING_ACCOUNT="REPLACE_WITH_FERGANA_BILLING_ACCOUNT_ID"
gcloud billing projects link $PROJECT_ID --billing-account=$BILLING_ACCOUNT
```

If the billing link fails, the user may need to accept an invitation. Check:
```bash
gcloud billing accounts list
```

---

## Phase 3: Enable APIs

```bash
gcloud services enable \
  gmail.googleapis.com \
  calendar-json.googleapis.com \
  pubsub.googleapis.com \
  run.googleapis.com \
  firestore.googleapis.com \
  aiplatform.googleapis.com \
  artifactregistry.googleapis.com \
  cloudresourcemanager.googleapis.com \
  iap.googleapis.com
```

---

## Phase 4: Infrastructure

### 4.1 Firestore

```bash
gcloud firestore databases create --location=us-central1 --type=firestore-native
```

### 4.2 Pub/Sub

```bash
# Generate a random webhook token
WEBHOOK_TOKEN=$(openssl rand -hex 16)

# Create topic
gcloud pubsub topics create gmail-push

# Grant Gmail permission to publish
gcloud pubsub topics add-iam-policy-binding gmail-push \
  --member="serviceAccount:gmail-api-push@system.gserviceaccount.com" \
  --role="roles/pubsub.publisher"
```

The push subscription will be created after Cloud Run deploys (we need the URL).

---

## Phase 5: OAuth Credentials

### 5.1 Create OAuth consent screen

```bash
# Get the project number
PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format='value(projectNumber)')

# Create the OAuth brand (internal type for Workspace)
gcloud alpha iap oauth-brands create \
  --application_title="Scheduled" \
  --support_email="$ACCOUNT_EMAIL"
```

If the `gcloud alpha iap` command fails, create the OAuth consent screen manually:

```bash
# Fallback: use REST API
ACCESS_TOKEN=$(gcloud auth print-access-token)
curl -s -X POST \
  "https://oauth2.googleapis.com/v1/projects/$PROJECT_ID/brands" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"applicationTitle\": \"Scheduled\",
    \"supportEmail\": \"$ACCOUNT_EMAIL\"
  }" || echo "Brand may already exist, continuing..."
```

### 5.2 Create OAuth client ID

```bash
ACCESS_TOKEN=$(gcloud auth print-access-token)

# Create OAuth client
OAUTH_RESPONSE=$(curl -s -X POST \
  "https://oauth2.googleapis.com/v1/projects/$PROJECT_ID/brands/-/identityAwareProxyClients" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"displayName": "Scheduled"}')

# Extract client ID and secret
GOOGLE_CLIENT_ID=$(echo $OAUTH_RESPONSE | python3 -c "import sys,json; print(json.load(sys.stdin).get('name','').split('/')[-1])")
GOOGLE_CLIENT_SECRET=$(echo $OAUTH_RESPONSE | python3 -c "import sys,json; print(json.load(sys.stdin).get('secret',''))")

echo "OAuth Client ID: $GOOGLE_CLIENT_ID"
```

If the IAP-based OAuth creation doesn't work for Gmail/Calendar scopes, fall back to creating OAuth credentials through the Google Cloud Console:

```bash
echo ""
echo "=== MANUAL STEP NEEDED ==="
echo "Go to: https://console.cloud.google.com/apis/credentials?project=$PROJECT_ID"
echo ""
echo "1. Click 'Create Credentials' > 'OAuth client ID'"
echo "2. Application type: 'Web application'"
echo "3. Name: 'Scheduled'"
echo "4. Authorized redirect URIs: (leave blank for now, we'll update after deploy)"
echo "5. Click 'Create'"
echo "6. Copy the Client ID and Client Secret"
echo ""
read -p "Paste Client ID: " GOOGLE_CLIENT_ID
read -p "Paste Client Secret: " GOOGLE_CLIENT_SECRET
```

---

## Phase 6: Deploy to Cloud Run

### 6.1 Generate session secret

```bash
SESSION_SECRET=$(openssl rand -hex 32)
```

### 6.2 Deploy

```bash
gcloud run deploy scheduler \
  --image=gcr.io/fergana-labs/scheduler:latest \
  --region=us-central1 \
  --platform=managed \
  --allow-unauthenticated \
  --min-instances=1 \
  --max-instances=2 \
  --memory=1Gi \
  --cpu=1 \
  --timeout=300 \
  --set-env-vars="\
GCP_PROJECT_ID=$PROJECT_ID,\
GCP_REGION=us-central1,\
GOOGLE_CLIENT_ID=$GOOGLE_CLIENT_ID,\
GOOGLE_CLIENT_SECRET=$GOOGLE_CLIENT_SECRET,\
SESSION_SECRET=$SESSION_SECRET,\
GMAIL_PUBSUB_TOPIC=projects/$PROJECT_ID/topics/gmail-push,\
GMAIL_WEBHOOK_TOKEN=$WEBHOOK_TOKEN,\
CONTROL_PLANE_PUBLIC_URL=PLACEHOLDER"
```

### 6.3 Get the Cloud Run URL and update config

```bash
CLOUD_RUN_URL=$(gcloud run services describe scheduler --region=us-central1 --format='value(status.url)')
echo "Deployed to: $CLOUD_RUN_URL"

# Update env vars with the real URL
gcloud run services update scheduler \
  --region=us-central1 \
  --update-env-vars="\
CONTROL_PLANE_PUBLIC_URL=$CLOUD_RUN_URL,\
WEB_APP_URL=$CLOUD_RUN_URL,\
GOOGLE_REDIRECT_URI=$CLOUD_RUN_URL,\
GOOGLE_WEB_REDIRECT_URI=$CLOUD_RUN_URL"
```

### 6.4 Update OAuth redirect URI

```bash
echo ""
echo "=== UPDATE OAUTH REDIRECT URI ==="
echo "Go to: https://console.cloud.google.com/apis/credentials?project=$PROJECT_ID"
echo "Edit the OAuth client and add this authorized redirect URI:"
echo "  $CLOUD_RUN_URL"
echo ""
echo "Press Enter when done..."
read
```

### 6.5 Create Pub/Sub push subscription

```bash
gcloud pubsub subscriptions create gmail-push-sub \
  --topic=gmail-push \
  --push-endpoint="$CLOUD_RUN_URL/webhooks/gmail?token=$WEBHOOK_TOKEN" \
  --ack-deadline=60
```

---

## Phase 7: Egress Lockdown (Network Security)

Restrict outbound traffic to Google APIs only. This ensures the app cannot send data anywhere except Google services.

```bash
# Create a VPC connector for Cloud Run
gcloud compute networks create scheduler-vpc --subnet-mode=auto

gcloud compute networks vpc-access connectors create scheduler-connector \
  --region=us-central1 \
  --network=scheduler-vpc \
  --range=10.8.0.0/28

# Create firewall rule: allow only Google API ranges
# Google publishes their IP ranges; for simplicity, we allow DNS-based egress
# Cloud Run with VPC connector + firewall rules restricting egress
gcloud compute firewall-rules create allow-google-apis-only \
  --network=scheduler-vpc \
  --direction=EGRESS \
  --action=ALLOW \
  --rules=tcp:443 \
  --destination-ranges=199.36.153.4/30,199.36.153.8/30 \
  --priority=1000

gcloud compute firewall-rules create deny-all-egress \
  --network=scheduler-vpc \
  --direction=EGRESS \
  --action=DENY \
  --rules=all \
  --destination-ranges=0.0.0.0/0 \
  --priority=2000

# Update Cloud Run to use the VPC connector
gcloud run services update scheduler \
  --region=us-central1 \
  --vpc-connector=scheduler-connector \
  --vpc-egress=all-traffic
```

If the VPC setup fails or is too complex, this step can be skipped. The app still provides data sovereignty — the code is open source and auditable.

---

## Phase 8: User OAuth

Open the browser for the user to authorize Gmail and Calendar access:

```bash
echo "Opening browser for Google authorization..."
open "$CLOUD_RUN_URL/auth/google"
```

The user clicks "Allow" to grant Gmail and Calendar access. Since this is a Workspace internal app, there is no "unverified app" warning.

Wait for the OAuth callback to complete:

```bash
echo "Waiting for OAuth to complete..."
sleep 5

# Check if the user was created
curl -s "$CLOUD_RUN_URL/" | python3 -c "import sys; print('Health check:', sys.stdin.read()[:100])"
```

---

## Phase 9: Onboarding

The onboarding agents (calendar backfill, scheduling preferences, email style analysis) should start automatically after OAuth. Check the status:

```bash
# Get a session token first
# The OAuth callback should have triggered onboarding automatically.
# Check Cloud Run logs to verify:
gcloud run services logs read scheduler --region=us-central1 --limit=20
```

---

## Phase 10: Verify

```bash
echo ""
echo "==================================="
echo "  Scheduled is set up!"
echo "==================================="
echo ""
echo "  Settings: $CLOUD_RUN_URL/settings"
echo "  Project:  $PROJECT_ID"
echo ""
echo "  How it works:"
echo "  1. Someone emails you to schedule a meeting"
echo "  2. Scheduled reads the email and checks your calendar"
echo "  3. A draft reply appears in your Gmail with proposed times"
echo "  4. You review and send (or edit first)"
echo ""
echo "  To check logs:  gcloud run services logs read scheduler --region=us-central1"
echo "  To update:       gcloud run services update scheduler --region=us-central1 --image=gcr.io/fergana-labs/scheduler:latest"
echo ""
```
