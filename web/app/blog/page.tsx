import { getAllBlogPosts } from '@/lib/blog-posts';
import Header from '@/components/landing/Header';
import Footer from '@/components/landing/Footer';
import BlogPageClient from '@/components/blog/BlogPageClient';
import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Blog | Stash',
  description:
    'Explore use cases, comparisons, and guides for AI-powered workflow automation.',
};

export default function BlogPage() {
  const allPosts = getAllBlogPosts();

  return (
    <div className="min-h-screen bg-[#F5F5F0]">
      <Header />

      <div className="py-24 sm:py-32">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <BlogPageClient allPosts={allPosts} />
        </div>
      </div>

      <Footer />
    </div>
  );
}
