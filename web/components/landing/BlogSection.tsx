'use client';

import Link from 'next/link';
import { ArrowRight } from 'lucide-react';

const featuredPost = {
  slug: 'six-reasons-agents-terrible-for-knowledge-work',
  title:
    'The Six Reasons Why Agents Are Great for Code but Terrible for Knowledge Work',
  description:
    'Despite the near-human capabilities of AI coding agents, the jobs of most knowledge workers still look the same today. This paradox is what drove us to build Scheduled.',
  category: 'Thoughts',
};

const otherPosts = [
  {
    slug: 'scheduled-vs-calendly',
    title: 'Scheduled vs Calendly & Cal.com: AI Drafts vs Scheduling Links',
    description:
      'AI-powered email drafts versus traditional scheduling link tools — which approach actually eliminates more friction?',
    category: 'Comparisons',
  },
  {
    slug: 'best-ai-scheduling-tools',
    title: 'Best AI Scheduling Tools in 2026',
    description:
      'A comprehensive comparison of Scheduled, Fyxer, Superhuman, Blockit, Poke, Howie, and Spark across features, pricing, and privacy.',
    category: 'Comparisons',
  },
  {
    slug: 'scheduled-case-study',
    title: 'The Tyranny of Scheduling',
    description:
      'Scheduling is the laundry of startup life. It barely takes any time, but the mental friction is enormous. Here is how we built Scheduled to make it disappear.',
    category: 'Case Studies',
  },
];

export default function BlogSection() {
  return (
    <section className="px-4 py-20 sm:px-6 sm:py-28 lg:py-32">
      <div className="mx-auto max-w-7xl">
        <div className="mb-16 text-center">
          <p className="text-sm font-medium uppercase tracking-widest text-[#43614a]">
            Blog
          </p>
          <h2 className="font-[family-name:var(--font-playfair)] mt-4 text-3xl font-normal italic tracking-tight text-gray-900 sm:text-4xl lg:text-5xl">
            Latest from the blog
          </h2>
          <p className="mx-auto mt-6 max-w-xl text-base leading-relaxed text-gray-500 sm:text-lg">
            Comparisons, case studies, and insights on AI-powered scheduling
          </p>
        </div>

        {/* Featured post - full width */}
        <Link
          href={`/blog/${featuredPost.slug}`}
          className="group mb-6 block overflow-hidden rounded-xl border border-gray-200 bg-white shadow-sm transition-all duration-200 hover:-translate-y-1 hover:shadow-lg"
        >
          <div className="p-8 sm:p-10">
            <div className="mb-4">
              <span className="inline-flex items-center rounded-full bg-green-50 px-3 py-1 text-xs font-medium text-[#43614a]">
                {featuredPost.category}
              </span>
            </div>
            <h3 className="mb-4 text-2xl font-semibold text-gray-900 transition-colors group-hover:text-[#43614a] sm:text-3xl">
              {featuredPost.title}
            </h3>
            <p className="mb-6 max-w-2xl text-base leading-relaxed text-gray-500">
              {featuredPost.description}
            </p>
            <div className="flex items-center text-sm font-medium text-[#43614a]">
              Read more
              <ArrowRight className="ml-1 h-4 w-4 transition-transform group-hover:translate-x-1" />
            </div>
          </div>
        </Link>

        {/* Other posts - 3 column grid */}
        <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {otherPosts.map(post => (
            <Link
              key={post.slug}
              href={`/blog/${post.slug}`}
              className="group flex flex-col overflow-hidden rounded-xl border border-gray-200 bg-white shadow-sm transition-all duration-200 hover:-translate-y-1 hover:shadow-lg"
            >
              <div className="flex flex-1 flex-col p-6">
                <div className="mb-3">
                  <span className="inline-flex items-center rounded-full bg-green-50 px-3 py-1 text-xs font-medium text-[#43614a]">
                    {post.category}
                  </span>
                </div>
                <h3 className="mb-3 text-lg font-semibold text-gray-900 transition-colors group-hover:text-[#43614a]">
                  {post.title}
                </h3>
                <p className="mb-4 flex-1 text-sm leading-relaxed text-gray-500">
                  {post.description}
                </p>
                <div className="flex items-center text-sm font-medium text-[#43614a]">
                  Read more
                  <ArrowRight className="ml-1 h-4 w-4 transition-transform group-hover:translate-x-1" />
                </div>
              </div>
            </Link>
          ))}
        </div>

        <div className="mt-12 text-center">
          <Link
            href="/blog"
            className="inline-flex items-center gap-2 text-sm font-medium text-gray-500 transition-colors hover:text-gray-900"
          >
            View all posts
            <ArrowRight className="h-4 w-4" />
          </Link>
        </div>
      </div>
    </section>
  );
}
