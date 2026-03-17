'use client';

import { useState } from 'react';
import Link from 'next/link';
import { BlogPost } from '@/lib/blog-posts';
import { Calendar, User, ArrowRight } from 'lucide-react';

interface BlogPageClientProps {
  allPosts: BlogPost[];
}

export default function BlogPageClient({ allPosts }: BlogPageClientProps) {
  const [selectedCategory, setSelectedCategory] = useState<string>('All');

  // Get unique categories (sorted for consistent rendering)
  const categories = [
    'All',
    ...Array.from(new Set(allPosts.map(post => post.category))).sort(),
  ];

  // Filter posts based on selected category
  const filteredPosts =
    selectedCategory === 'All'
      ? allPosts
      : allPosts.filter(post => post.category === selectedCategory);

  return (
    <>
      {/* Header */}
      <div className="mb-12 text-center">
        <h1 className="font-[family-name:var(--font-space-grotesk)] text-4xl font-bold tracking-tight text-gray-900 sm:text-5xl">
          Blog
        </h1>
        <p className="mx-auto mt-4 max-w-2xl text-lg text-gray-600">
          Insights, use cases, and updates from the Stash team
        </p>
      </div>

      {/* Category Filter */}
      <div className="mb-8 flex flex-wrap justify-center gap-2">
        {categories.map(category => (
          <button
            key={category}
            onClick={() => setSelectedCategory(category)}
            className={`cursor-pointer rounded-full px-4 py-2 text-sm font-medium transition-all duration-200 ${
              selectedCategory === category
                ? 'bg-[#43614a] text-white shadow-sm'
                : 'border border-gray-200 bg-white text-gray-700 hover:bg-gray-50'
            }`}
          >
            {category}
          </button>
        ))}
      </div>

      {/* Post Count */}
      <div className="mb-6 text-center text-sm text-gray-500">
        {filteredPosts.length} {filteredPosts.length === 1 ? 'post' : 'posts'}
      </div>

      {/* Blog Posts Grid */}
      <div className="grid gap-8 lg:grid-cols-2">
        {filteredPosts.map(post => (
          <Link
            key={post.slug}
            href={`/blog/${post.slug}`}
            className="group relative flex flex-col overflow-hidden rounded-xl border border-gray-200 bg-[#F5F5F0] shadow-sm transition-all duration-200 hover:-translate-y-1 hover:shadow-lg"
          >
            <div className="flex-1 p-6">
              {/* Category Badge */}
              <div className="mb-3">
                <span className="inline-flex items-center rounded-full bg-green-50 px-3 py-1 text-xs font-medium text-[#43614a]">
                  {post.category}
                </span>
              </div>

              {/* Title */}
              <h2 className="mb-3 text-xl font-semibold text-gray-900 transition-colors group-hover:text-[#43614a]">
                {post.title}
              </h2>

              {/* Description */}
              <p className="mb-4 line-clamp-2 text-sm text-gray-600">
                {post.description}
              </p>

              {/* Meta Info */}
              <div className="flex items-center gap-4 text-xs text-gray-500">
                <div className="flex items-center gap-1">
                  <Calendar className="h-3 w-3" />
                  <time dateTime={post.date}>
                    {new Date(post.date).toLocaleDateString('en-US', {
                      year: 'numeric',
                      month: 'long',
                      day: 'numeric',
                    })}
                  </time>
                </div>
                <div className="flex items-center gap-1">
                  <User className="h-3 w-3" />
                  <span>{post.author}</span>
                </div>
              </div>
            </div>

            {/* Read More Link */}
            <div className="px-6 pb-6">
              <div className="flex items-center text-sm font-medium text-[#43614a]">
                Read more
                <ArrowRight className="ml-1 h-4 w-4 transition-transform group-hover:translate-x-1" />
              </div>
            </div>
          </Link>
        ))}
      </div>
    </>
  );
}
