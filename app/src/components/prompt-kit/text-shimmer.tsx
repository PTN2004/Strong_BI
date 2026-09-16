import React from 'react';
import { cn } from '@/lib/utils';

// TextShimmer — cùng API với prompt-kit (https://www.prompt-kit.com) nhưng thuần CSS
// (không cần framer-motion): dải sáng quét qua chữ, dùng cho các text trạng thái loading.
// Màu tuỳ biến qua CSS vars --ts-base (nền chữ) và --ts-shine (dải sáng).
interface TextShimmerProps {
  children: React.ReactNode;
  className?: string;
  duration?: number; // giây / 1 vòng quét
  as?: React.ElementType;
}

export function TextShimmer({ children, className, duration = 1.6, as: Tag = 'span' }: TextShimmerProps) {
  return (
    <Tag
      className={cn('inline-block bg-clip-text text-transparent select-none', className)}
      style={{
        // --primary của app là màu oklch đầy đủ → pha độ mờ bằng color-mix
        backgroundImage:
          'linear-gradient(90deg, var(--ts-base, color-mix(in oklab, var(--primary) 45%, transparent)) 0%, var(--ts-base, color-mix(in oklab, var(--primary) 45%, transparent)) 42%, var(--ts-shine, var(--primary)) 50%, var(--ts-base, color-mix(in oklab, var(--primary) 45%, transparent)) 58%, var(--ts-base, color-mix(in oklab, var(--primary) 45%, transparent)) 100%)',
        backgroundSize: '200% 100%',
        animation: `text-shimmer ${duration}s linear infinite`,
      }}
    >
      {children}
    </Tag>
  );
}

export default TextShimmer;
