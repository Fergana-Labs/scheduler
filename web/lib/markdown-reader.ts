import type { BlogPost } from './blog-posts';

const STASH_DESKTOP_DOWNLOAD_URL = 'https://stash.ac';

/**
 * Read all blog posts from markdown files (server-side only)
 * This function uses Node.js fs module and should only be called at build time or on the server
 */
export function readMarkdownPosts(): BlogPost[] {
  // Only run on server side (not in browser)
  if (typeof window !== 'undefined') {
    return [];
  }

  try {
    // Dynamic imports for Node.js modules (only available server-side)
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    const fs = require('fs');
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    const path = require('path');
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    const matter = require('gray-matter');

    const contentDirectory = path.join(process.cwd(), 'content', 'blog');

    if (!fs.existsSync(contentDirectory)) {
      return [];
    }

    /**
     * Recursively read all markdown files from a directory
     */
    function getAllMarkdownFiles(
      dir: string,
      fileList: string[] = []
    ): string[] {
      const files = fs.readdirSync(dir);

      files.forEach((file: string) => {
        const filePath = path.join(dir, file);
        const stat = fs.statSync(filePath);

        if (stat.isDirectory()) {
          getAllMarkdownFiles(filePath, fileList);
        } else if (file.endsWith('.md')) {
          fileList.push(filePath);
        }
      });

      return fileList;
    }

    const markdownFiles = getAllMarkdownFiles(contentDirectory);
    const posts: BlogPost[] = [];

    markdownFiles.forEach((filePath: string) => {
      try {
        const fileContents = fs.readFileSync(filePath, 'utf8');
        const { data, content } = matter(fileContents);

        // Validate required fields
        if (
          !data.slug ||
          !data.title ||
          !data.description ||
          !data.date ||
          !data.author ||
          !data.category
        ) {
          console.warn(
            `Skipping ${filePath}: missing required frontmatter fields`
          );
          return;
        }

        // Replace placeholder with actual download URL
        const processedContent = content
          .trim()
          .replace(
            /\{\{STASH_DESKTOP_DOWNLOAD_URL\}\}/g,
            STASH_DESKTOP_DOWNLOAD_URL
          );

        posts.push({
          slug: data.slug,
          title: data.title,
          description: data.description,
          date: data.date,
          author: data.author,
          category: data.category,
          keywords: data.keywords,
          metaDescription: data.metaDescription,
          content: processedContent,
        });
      } catch (error) {
        console.error(`Error reading ${filePath}:`, error);
      }
    });

    return posts;
  } catch (error) {
    console.error('Error reading markdown posts:', error);
    return [];
  }
}
