import type { Metadata } from 'next';
import Header from '@/components/landing/Header';
import Footer from '@/components/landing/Footer';

export const metadata: Metadata = {
  title: 'Privacy Policy | Stash',
  description:
    'Learn how Stash by Fergana Labs collects, uses, and protects your personal information.',
};

export default function PrivacyPolicy() {
  return (
    <div className="min-h-screen bg-[#F5F5F0]">
      <Header />
      <div className="mx-auto max-w-4xl px-4 py-24 sm:py-32">
        <div className="space-y-8">
          <div className="space-y-4 text-center">
            <h1 className="text-4xl font-bold tracking-tight">Privacy Policy</h1>
            <p className="text-gray-600">Last updated: September 15, 2025</p>
          </div>

          <div className="border-t border-gray-200"></div>

          <div className="space-y-6">
            <section className="space-y-4">
              <h2 className="text-2xl font-semibold">Introduction</h2>
              <p className="leading-relaxed text-gray-600">
                Fergana Labs Inc. {`("we," "our," or "us")`} respects your privacy
                and is committed to protecting your personal information. This
                Privacy Policy explains how we collect, use, disclose, and
                safeguard your information when you use our Stash application{' '}
                {`("the App")`}, a web-based platform that provides AI-powered
                file management, document collaboration, and intelligent chat
                features.
              </p>
            </section>

            <section className="space-y-4">
              <h2 className="text-2xl font-semibold">Information We Collect</h2>

              <div className="space-y-4">
                <h3 className="text-xl font-medium">Personal Information</h3>
                <ul className="ml-4 list-inside list-disc space-y-2 text-gray-600">
                  <li>
                    Account information (name, email address) when you sign in
                  </li>
                  <li>User preferences and settings</li>
                  <li>Workspace and folder organization preferences</li>
                </ul>
              </div>

              <div className="space-y-4">
                <h3 className="text-xl font-medium">File and Content Data</h3>
                <ul className="ml-4 list-inside list-disc space-y-2 text-gray-600">
                  <li>
                    Files you upload to workspaces (documents, PDFs, images, etc.)
                  </li>
                  <li>File metadata (names, sizes, types, creation dates)</li>
                  <li>Document content and edits for real-time collaboration</li>
                  <li>File embeddings for semantic search capabilities</li>
                </ul>
              </div>

              <div className="space-y-4">
                <h3 className="text-xl font-medium">
                  Chat and AI Interaction Data
                </h3>
                <ul className="ml-4 list-inside list-disc space-y-2 text-gray-600">
                  <li>Chat messages and conversation history</li>
                  <li>AI assistant responses and interactions</li>
                  <li>Memory entries you create to personalize AI responses</li>
                </ul>
              </div>

              <div className="space-y-4">
                <h3 className="text-xl font-medium">Usage Data</h3>
                <ul className="ml-4 list-inside list-disc space-y-2 text-gray-600">
                  <li>Application usage patterns and feature interactions</li>
                  <li>Performance and error data</li>
                  <li>Browser and device information</li>
                </ul>
              </div>
            </section>

            <section className="space-y-4">
              <h2 className="text-2xl font-semibold">
                How We Use Your Information
              </h2>
              <ul className="ml-4 list-inside list-disc space-y-2 text-gray-600">
                <li>Store and manage your files, workspaces, and folders</li>
                <li>Enable real-time collaborative document editing</li>
                <li>
                  Provide AI-powered chat responses based on your files and
                  conversations
                </li>
                <li>
                  Generate embeddings for semantic search across your documents
                </li>
                <li>
                  Integrate with Google Drive and Gmail for enhanced productivity
                </li>
                <li>Sync your workspaces and preferences across sessions</li>
                <li>Improve our AI models and services</li>
                <li>Provide customer support and respond to inquiries</li>
                <li>Ensure security and prevent unauthorized access</li>
              </ul>
            </section>

            <section className="space-y-4">
              <h2 className="text-2xl font-semibold">Privacy Controls</h2>

              <div className="space-y-4">
                <h3 className="text-xl font-medium">Workspace Access</h3>
                <p className="leading-relaxed text-gray-600">
                  You have full control over your workspaces. You can create
                  private workspaces or share them with collaborators. Only users
                  you explicitly grant access to can view your workspace files and
                  chats.
                </p>
              </div>

              <div className="space-y-4">
                <h3 className="text-xl font-medium">File Management</h3>
                <p className="leading-relaxed text-gray-600">
                  You can delete files, folders, and entire workspaces at any
                  time. Deleted files are permanently removed from our systems.
                </p>
              </div>

              <div className="space-y-4">
                <h3 className="text-xl font-medium">AI Memory Settings</h3>
                <p className="leading-relaxed text-gray-600">
                  You can manage AI memories in the Settings section to
                  personalize how the AI assistant responds to you. These memories
                  can be viewed, edited, or deleted at any time.
                </p>
              </div>

              <div className="space-y-4">
                <h3 className="text-xl font-medium">Third-Party Integrations</h3>
                <p className="leading-relaxed text-gray-600">
                  Google Drive and Gmail integrations are optional. You can
                  connect or disconnect these services at any time through the
                  Settings page.
                </p>
              </div>
            </section>

            <section className="space-y-4">
              <h2 className="text-2xl font-semibold">
                Data Storage and Retention
              </h2>
              <ul className="ml-4 list-inside list-disc space-y-2 text-gray-600">
                <li>
                  Account and preference data is stored securely in encrypted
                  databases (PostgreSQL)
                </li>
                <li>
                  Files are stored securely with appropriate access controls
                </li>
                <li>
                  Document collaboration data is stored using Yjs for real-time
                  synchronization
                </li>
                <li>
                  Chat history and AI interactions are retained to maintain
                  conversation context
                </li>
                <li>File embeddings are stored for search functionality</li>
                <li>
                  You may delete individual files, chats, or your entire account
                  at any time
                </li>
                <li>
                  You may request complete data deletion by contacting
                  support@ferganalabs.com
                </li>
                <li>
                  We retain data only as long as necessary to provide our services
                </li>
              </ul>
            </section>

            <section className="space-y-4">
              <h2 className="text-2xl font-semibold">
                Data Sharing and Disclosure
              </h2>
              <p className="leading-relaxed text-gray-600">
                We do not sell, trade, or rent your personal information to third
                parties. We may share your information only in the following
                circumstances:
              </p>
              <ul className="ml-4 list-inside list-disc space-y-2 text-gray-600">
                <li>
                  With AI service providers to generate suggestions (data is
                  anonymized when possible)
                </li>
                <li>
                  With cloud infrastructure providers for secure data storage and
                  processing
                </li>
                <li>
                  When required by law or to protect our rights and the safety of
                  our users
                </li>
                <li>
                  In connection with a business transaction (merger, acquisition,
                  etc.)
                </li>
              </ul>
            </section>

            <section className="space-y-4">
              <h2 className="text-2xl font-semibold">Security</h2>
              <p className="leading-relaxed text-gray-600">
                We implement appropriate technical and organizational security
                measures to protect your information against unauthorized access,
                alteration, disclosure, or destruction. However, no method of
                transmission over the internet or electronic storage is 100%
                secure.
              </p>
            </section>

            <section className="space-y-4">
              <h2 className="text-2xl font-semibold">Third-Party Services</h2>
              <p className="leading-relaxed text-gray-600">
                Stash may integrate with (but limited to) the following
                third-party services to enhance functionality:
              </p>
              <ul className="ml-4 list-inside list-disc space-y-2 text-gray-600">
                <li>
                  <strong>Clerk:</strong> Authentication and user management
                </li>
                <li>
                  <strong>Anthropic:</strong> AI chat and content generation
                </li>
                <li>
                  <strong>OpenAI:</strong> AI chat and content generation
                </li>
                <li>
                  <strong>Google Drive:</strong> Optional integration for
                  importing/exporting files
                </li>
                <li>
                  <strong>Gmail:</strong> Optional integration for email
                  assistance
                </li>
              </ul>
              <p className="mt-4 leading-relaxed text-gray-600">
                Each integration is subject to its own privacy policy. Optional
                integrations can be connected or disconnected at any time.
              </p>
            </section>

            <section className="space-y-4">
              <h2 className="text-2xl font-semibold">{"Children's Privacy"}</h2>
              <p className="leading-relaxed text-gray-600">
                Our service is not intended for children under 13 years of age. We
                do not knowingly collect personal information from children under
                13. If you are a parent or guardian and believe your child has
                provided us with personal information, please contact us so we can
                delete such information.
              </p>
            </section>

            <section className="space-y-4">
              <h2 className="text-2xl font-semibold">
                Changes to This Privacy Policy
              </h2>
              <p className="leading-relaxed text-gray-600">
                We may update this Privacy Policy from time to time. We will
                notify you of any changes by posting the new Privacy Policy on
                this page and updating the {`"Last updated"`} date. You are
                advised to review this Privacy Policy periodically for any
                changes.
              </p>
            </section>

            <section className="space-y-4">
              <h2 className="text-2xl font-semibold">Contact Us</h2>
              <p className="leading-relaxed text-gray-600">
                If you have any questions about this Privacy Policy or our privacy
                practices, please contact us at:
              </p>
              <div className="mt-4 rounded-lg bg-gray-100 p-4">
                <p className="font-medium">Fergana Labs Inc.</p>
                <p>Email: support@ferganalabs.com</p>
                <p>Website: https://ferganalabs.com</p>
              </div>
            </section>
          </div>
        </div>
      </div>
      <Footer />
    </div>
  );
}
