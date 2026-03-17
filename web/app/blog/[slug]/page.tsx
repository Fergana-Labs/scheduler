import { notFound } from 'next/navigation';
import Link from 'next/link';
import { getBlogPost, getAllBlogPosts } from '@/lib/blog-posts';
import Header from '@/components/landing/Header';
import Footer from '@/components/landing/Footer';
import { Calendar, User, ArrowLeft } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import type { Metadata } from 'next';

export async function generateStaticParams() {
  const posts = getAllBlogPosts();
  return posts.map(post => ({
    slug: post.slug,
  }));
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ slug: string }>;
}): Promise<Metadata> {
  const { slug } = await params;
  const post = getBlogPost(slug);

  if (!post) {
    return {
      title: 'Blog Post Not Found | Stash',
      description: 'The requested blog post could not be found.',
    };
  }

  return {
    title: `${post.title} | Stash`,
    description: post.metaDescription || post.description,
    keywords: post.keywords,
    authors: [{ name: post.author }],
  };
}

export default async function BlogPostPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const post = getBlogPost(slug);

  if (!post) {
    notFound();
  }

  const articleSchema = {
    '@context': 'https://schema.org',
    '@type': 'Article',
    headline: post.title,
    description: post.description,
    datePublished: post.date,
    dateModified: post.date,
    author: {
      '@type': 'Organization',
      name: 'Fergana Labs',
    },
    publisher: {
      '@type': 'Organization',
      name: 'Fergana Labs',
    },
    keywords: post.keywords || '',
  };

  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(articleSchema) }}
      />
      <div className="min-h-screen bg-[#F5F5F0]">
        <Header />

        <article className="py-24 sm:py-32">
          <div className="mx-auto max-w-3xl px-4 sm:px-6 lg:px-8">
            {/* Back Link */}
            <Link
              href="/blog"
              className="mb-8 inline-flex items-center text-sm text-gray-600 hover:text-gray-900"
            >
              <ArrowLeft className="mr-1 h-4 w-4" />
              Back to blog
            </Link>

            {/* Category Badge */}
            <div className="mb-4">
              <span className="inline-flex items-center rounded-full bg-green-50 px-3 py-1.5 text-sm font-medium text-[#43614a]">
                {post.category}
              </span>
            </div>

            {/* Title */}
            <h1 className="mb-4 font-[family-name:var(--font-space-grotesk)] text-4xl font-bold tracking-tight text-gray-900 sm:text-5xl">
              {post.title}
            </h1>

            {/* Description */}
            <p className="mb-6 text-xl text-gray-600">{post.description}</p>

            {/* Meta Info */}
            <div className="mb-8 flex items-center gap-6 border-b border-gray-200 pb-8 text-sm text-gray-500">
              <div className="flex items-center gap-2">
                <Calendar className="h-4 w-4" />
                <time dateTime={post.date}>
                  {new Date(post.date).toLocaleDateString('en-US', {
                    year: 'numeric',
                    month: 'long',
                    day: 'numeric',
                  })}
                </time>
              </div>
              <div className="flex items-center gap-2">
                <User className="h-4 w-4" />
                <span>{post.author}</span>
              </div>
            </div>

            {/* Content */}
            <div className="prose prose-lg max-w-none">
              <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                components={{
                  h1({ children }) {
                    return (
                      <h1 className="mt-8 mb-4 text-3xl font-bold text-gray-900">
                        {children}
                      </h1>
                    );
                  },
                  h2({ children }) {
                    return (
                      <h2 className="mt-8 mb-4 text-2xl font-bold text-gray-900">
                        {children}
                      </h2>
                    );
                  },
                  h3({ children }) {
                    return (
                      <h3 className="mt-6 mb-3 text-xl font-semibold text-gray-900">
                        {children}
                      </h3>
                    );
                  },
                  p({ children }) {
                    return (
                      <p className="mb-4 leading-relaxed text-gray-700">
                        {children}
                      </p>
                    );
                  },
                  ul({ children }) {
                    return (
                      <ul className="mb-4 list-disc space-y-2 pl-6">
                        {children}
                      </ul>
                    );
                  },
                  ol({ children }) {
                    return (
                      <ol className="mb-4 list-decimal space-y-2 pl-6">
                        {children}
                      </ol>
                    );
                  },
                  li({ children }) {
                    return <li className="text-gray-700">{children}</li>;
                  },
                  strong({ children }) {
                    return (
                      <strong className="font-semibold text-gray-900">
                        {children}
                      </strong>
                    );
                  },
                  a({ href, children }) {
                    return (
                      <a
                        href={href}
                        className="text-[#43614a] underline hover:text-[#527559]"
                        target={href?.startsWith('http') ? '_blank' : undefined}
                        rel={
                          href?.startsWith('http')
                            ? 'noopener noreferrer'
                            : undefined
                        }
                      >
                        {children}
                      </a>
                    );
                  },
                  blockquote({ children }) {
                    return (
                      <blockquote className="my-4 border-l-4 border-[#43614a] pl-4 text-gray-700 italic">
                        {children}
                      </blockquote>
                    );
                  },
                  code({ children }) {
                    return (
                      <code className="rounded bg-gray-100 px-1.5 py-0.5 font-mono text-sm text-gray-900">
                        {children}
                      </code>
                    );
                  },
                  table({ children }) {
                    return (
                      <div className="my-6 overflow-x-auto">
                        <table className="min-w-full divide-y divide-gray-300 border border-gray-300">
                          {children}
                        </table>
                      </div>
                    );
                  },
                  thead({ children }) {
                    return <thead className="bg-gray-50">{children}</thead>;
                  },
                  tbody({ children }) {
                    return (
                      <tbody className="divide-y divide-gray-200 bg-white">
                        {children}
                      </tbody>
                    );
                  },
                  tr({ children }) {
                    return <tr>{children}</tr>;
                  },
                  th({ children }) {
                    return (
                      <th className="px-4 py-3 text-left text-sm font-semibold text-gray-900">
                        {children}
                      </th>
                    );
                  },
                  td({ children }) {
                    return (
                      <td className="px-4 py-3 text-sm text-gray-700">
                        {children}
                      </td>
                    );
                  },
                }}
              >
                {post.content}
              </ReactMarkdown>
            </div>
          </div>
        </article>

        <Footer />
      </div>
    </>
  );
}
