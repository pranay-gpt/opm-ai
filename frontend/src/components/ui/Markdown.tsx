import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { useResolvedTheme } from '../../stores/useAppStore';

interface MarkdownProps {
  children: string;
  /** Extra classes appended after the prose defaults. */
  className?: string;
}

// Typography plugin defaults use its own gray palette, which ignores our CSS
// vars. These overrides pull headings/body/links/borders back onto the theme
// colors; prose-invert only flips the plugin's own defaults, so we still need
// both it and these.
const PROSE_THEME =
  'prose-headings:text-textPrimary prose-p:text-textPrimary prose-li:text-textPrimary ' +
  'prose-strong:text-textPrimary prose-a:text-primary hover:prose-a:text-primaryHover ' +
  'prose-code:text-textPrimary prose-code:font-mono prose-code:before:content-none ' +
  'prose-code:after:content-none prose-pre:bg-page prose-pre:border prose-pre:border-border ' +
  'prose-pre:text-textSecondary prose-blockquote:text-textSecondary ' +
  'prose-blockquote:border-border prose-hr:border-border prose-th:text-textPrimary ' +
  'prose-td:text-textSecondary';

/** Renders markdown (GFM) with the app's prose styling for the active theme. */
export default function Markdown({ children, className = '' }: MarkdownProps) {
  const theme = useResolvedTheme();
  return (
    <div
      className={`prose ${theme === 'dark' ? 'prose-invert' : ''} ${PROSE_THEME} max-w-none ${className}`}
    >
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{children}</ReactMarkdown>
    </div>
  );
}
