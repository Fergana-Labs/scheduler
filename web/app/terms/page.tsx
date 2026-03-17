import type { Metadata } from 'next';
import Header from '@/components/landing/Header';
import Footer from '@/components/landing/Footer';

export const metadata: Metadata = {
  title: 'Terms of Service | Stash',
  description:
    'Read the terms of service for Stash by Fergana Labs. Understand your rights and responsibilities when using our AI-powered platform.',
};

export default function TermsOfService() {
  return (
    <div className="min-h-screen bg-[#F5F5F0]">
      <Header />
      <div className="mx-auto max-w-4xl px-4 py-24 sm:py-32">
        <div className="space-y-8">
          <div className="space-y-4 text-center">
            <h1 className="text-4xl font-bold tracking-tight">
              Terms of Service
            </h1>
            <p className="text-gray-600">Last updated: September 15, 2025</p>
          </div>

          <div className="border-t border-gray-200"></div>

          <div className="space-y-6">
            <section className="space-y-4">
              <h2 className="text-2xl font-semibold">Agreement to Terms</h2>
              <p className="leading-relaxed text-gray-600">
                These Terms of Service {`("Terms")`} constitute a legally binding
                agreement between you and Fergana Labs Inc.{' '}
                {`("Company," "we," "our," or "us")`}
                concerning your access to and use of the Stash application{' '}
                {`("App" or "Service")`}, a web-based platform that provides
                AI-powered file management, document collaboration, and
                intelligent chat features.
              </p>
              <p className="leading-relaxed text-gray-600">
                By accessing or using our App, you agree to be bound by these
                Terms. If you do not agree to these Terms, do not use the App.
              </p>
            </section>

            <section className="space-y-4">
              <h2 className="text-2xl font-semibold">Description of Service</h2>
              <p className="leading-relaxed text-gray-600">
                Stash is a web-based platform that provides:
              </p>
              <ul className="ml-4 list-inside list-disc space-y-2 text-gray-600">
                <li>
                  File upload, storage, and organization in workspaces and folders
                </li>
                <li>Real-time collaborative document editing</li>
                <li>AI-powered chat with access to your files and documents</li>
                <li>Semantic search across your uploaded content</li>
                <li>
                  Google Drive and Gmail integrations for enhanced productivity
                </li>
                <li>Personalized AI memories to customize assistant responses</li>
                <li>Workspace sharing and collaboration features</li>
              </ul>
            </section>

            <section className="space-y-4">
              <h2 className="text-2xl font-semibold">
                User Accounts and Registration
              </h2>
              <ul className="ml-4 list-inside list-disc space-y-2 text-gray-600">
                <li>
                  You must create an account to access certain features of the App
                </li>
                <li>
                  You are responsible for maintaining the confidentiality of your
                  account credentials
                </li>
                <li>
                  You must provide accurate and complete information when creating
                  your account
                </li>
                <li>
                  You are responsible for all activities that occur under your
                  account
                </li>
                <li>
                  You must notify us immediately of any unauthorized use of your
                  account
                </li>
              </ul>
            </section>

            <section className="space-y-4">
              <h2 className="text-2xl font-semibold">Acceptable Use</h2>
              <p className="leading-relaxed text-gray-600">
                You agree to use the App only for lawful purposes and in
                accordance with these Terms. You agree not to:
              </p>
              <ul className="ml-4 list-inside list-disc space-y-2 text-gray-600">
                <li>
                  Use the App for any unlawful purpose or in violation of any
                  applicable laws
                </li>
                <li>
                  Upload, store, or share harmful, offensive, illegal, or
                  infringing content
                </li>
                <li>{`Attempt to gain unauthorized access to our systems, other users' accounts, or workspaces`}</li>
                <li>{`Interfere with or disrupt the App's functionality, servers, or other users' experience`}</li>
                <li>
                  Use the App to violate intellectual property rights or privacy
                  rights of others
                </li>
                <li>
                  Attempt to circumvent any security measures, access controls, or
                  usage limits
                </li>
                <li>
                  Use automated systems to scrape, data mine, or extract data from
                  the App
                </li>
                <li>
                  Share your account credentials or allow unauthorized access to
                  your account
                </li>
              </ul>
            </section>

            <section className="space-y-4">
              <h2 className="text-2xl font-semibold">Privacy and Data</h2>
              <ul className="ml-4 list-inside list-disc space-y-2 text-gray-600">
                <li>Your use of the App is subject to our Privacy Policy</li>
                <li>
                  You retain ownership of all files and content you upload to the
                  App
                </li>
                <li>
                  You control workspace access and can share or keep workspaces
                  private
                </li>
                <li>
                  We use AI services to provide chat responses, which involves
                  processing your data
                </li>
                <li>You may delete your files, chats, and data at any time</li>
                <li>
                  By uploading content, you grant us a license to store and
                  process it to provide our services
                </li>
              </ul>
            </section>

            <section className="space-y-4">
              <h2 className="text-2xl font-semibold">
                User Content and Responsibilities
              </h2>
              <ul className="ml-4 list-inside list-disc space-y-2 text-gray-600">
                <li>
                  You are responsible for the content you upload and share through
                  the App
                </li>
                <li>
                  You must have the necessary rights to upload and share any
                  content
                </li>
                <li>
                  You warrant that your content does not violate any laws or
                  third-party rights
                </li>
                <li>
                  We reserve the right to remove content that violates these Terms
                </li>
                <li>
                  You are responsible for maintaining backups of your important
                  content
                </li>
                <li>
                  File size limits and storage quotas may apply based on your
                  subscription tier
                </li>
              </ul>
            </section>

            <section className="space-y-4">
              <h2 className="text-2xl font-semibold">Intellectual Property</h2>
              <ul className="ml-4 list-inside list-disc space-y-2 text-gray-600">
                <li>
                  The App and its content are owned by Fergana Labs Inc. and
                  protected by intellectual property laws
                </li>
                <li>
                  You are granted a limited, non-exclusive, non-transferable
                  license to use the App
                </li>
                <li>You retain ownership of your original content and data</li>
                <li>
                  AI-generated suggestions become available to you under this
                  license
                </li>
                <li>
                  You may not use our trademarks, logos, or brand elements without
                  permission
                </li>
              </ul>
            </section>

            <section className="space-y-4">
              <h2 className="text-2xl font-semibold">
                Subscription and Payments
              </h2>
              <ul className="ml-4 list-inside list-disc space-y-2 text-gray-600">
                <li>Some features may require a paid subscription</li>
                <li>
                  Subscription fees are billed in advance on a recurring basis
                </li>
                <li>You may cancel your subscription at any time</li>
                <li>Refunds are provided according to our refund policy</li>
                <li>Prices are subject to change with notice</li>
              </ul>
            </section>

            <section className="space-y-4">
              <h2 className="text-2xl font-semibold">Service Availability</h2>
              <ul className="ml-4 list-inside list-disc space-y-2 text-gray-600">
                <li>
                  We strive to maintain high service availability but cannot
                  guarantee uninterrupted service
                </li>
                <li>
                  We may perform maintenance, updates, or modifications that
                  temporarily affect service
                </li>
                <li>
                  Some features depend on third-party AI services which may have
                  their own availability limitations
                </li>
                <li>
                  We reserve the right to modify or discontinue features with
                  reasonable notice
                </li>
              </ul>
            </section>

            <section className="space-y-4">
              <h2 className="text-2xl font-semibold">
                Disclaimers and Limitations of Liability
              </h2>

              <div className="space-y-4">
                <h3 className="text-xl font-medium">{`Service Provided "As Is"`}</h3>
                <p className="leading-relaxed text-gray-600">
                  The App is provided {`"as is" and "as available"`} without
                  warranties of any kind, either express or implied, including but
                  not limited to warranties of merchantability, fitness for a
                  particular purpose, or non-infringement.
                </p>
              </div>

              <div className="space-y-4">
                <h3 className="text-xl font-medium">AI Accuracy</h3>
                <p className="leading-relaxed text-gray-600">
                  We do not warrant that AI-generated responses will be accurate,
                  appropriate, or error-free. You are responsible for reviewing
                  and verifying all AI-generated content before use.{' '}
                  {`The AI assistant's`}
                  responses are based on the files and context you provide, and we
                  make no guarantees about their correctness.
                </p>
              </div>

              <div className="space-y-4">
                <h3 className="text-xl font-medium">Limitation of Liability</h3>
                <p className="leading-relaxed text-gray-600">
                  In no event shall Fergana Labs Inc. be liable for any indirect,
                  incidental, special, consequential, or punitive damages,
                  including but not limited to loss of profits, data, or other
                  intangible losses, resulting from your use of the App.
                </p>
              </div>
            </section>

            <section className="space-y-4">
              <h2 className="text-2xl font-semibold">Indemnification</h2>
              <p className="leading-relaxed text-gray-600">
                You agree to indemnify, defend, and hold harmless Fergana Labs
                Inc. and its officers, directors, employees, and agents from and
                against any claims, damages, losses, costs, and expenses{' '}
                {`(including reasonable attorneys' fees)`} arising from your use
                of the App or violation of these Terms.
              </p>
            </section>

            <section className="space-y-4">
              <h2 className="text-2xl font-semibold">Termination</h2>
              <ul className="ml-4 list-inside list-disc space-y-2 text-gray-600">
                <li>
                  You may terminate your account at any time by contacting support
                </li>
                <li>
                  We may suspend or terminate your access for violations of these
                  Terms
                </li>
                <li>
                  Upon termination, your right to use the App ceases immediately
                </li>
                <li>
                  Provisions that should survive termination will remain in effect
                </li>
              </ul>
            </section>

            <section className="space-y-4">
              <h2 className="text-2xl font-semibold">
                Governing Law and Dispute Resolution
              </h2>
              <ul className="ml-4 list-inside list-disc space-y-2 text-gray-600">
                <li>
                  These Terms are governed by the laws of the jurisdiction where
                  Fergana Labs Inc. is incorporated
                </li>
                <li>
                  Disputes will be resolved through binding arbitration or in
                  courts of competent jurisdiction
                </li>
                <li>
                  You waive the right to participate in class action lawsuits
                </li>
              </ul>
            </section>

            <section className="space-y-4">
              <h2 className="text-2xl font-semibold">Changes to Terms</h2>
              <p className="leading-relaxed text-gray-600">
                We reserve the right to modify these Terms at any time. We will
                notify you of any material changes by posting the updated Terms on
                this page and updating the {`"Last updated"`} date. Your continued
                use of the App after such changes constitutes acceptance of the
                new Terms.
              </p>
            </section>

            <section className="space-y-4">
              <h2 className="text-2xl font-semibold">Severability</h2>
              <p className="leading-relaxed text-gray-600">
                If any provision of these Terms is found to be unenforceable or
                invalid, that provision will be limited or eliminated to the
                minimum extent necessary so that these Terms will otherwise remain
                in full force and effect.
              </p>
            </section>

            <section className="space-y-4">
              <h2 className="text-2xl font-semibold">Contact Information</h2>
              <p className="leading-relaxed text-gray-600">
                If you have any questions about these Terms of Service, please
                contact us at:
              </p>
              <div className="mt-4 rounded-lg bg-gray-100 p-4">
                <p className="font-medium">Fergana Labs Inc.</p>
                <p>Email: support@ferganalabs.com</p>
                <p>Website: https://ferganalabs.com</p>
              </div>
            </section>

            <section className="space-y-4">
              <h2 className="text-2xl font-semibold">Effective Date</h2>
              <p className="leading-relaxed text-gray-600">
                These Terms of Service are effective as of September 15, 2025, and
                will remain in effect until replaced by updated terms.
              </p>
            </section>
          </div>
        </div>
      </div>
      <Footer />
    </div>
  );
}
