// =============================================================================
// pages/_document.tsx — Next.js custom Document
// =============================================================================
//
// PURPOSE
// -------
// Customizes the HTML shell:
//   - sets the lang attribute,
//   - preloads webfonts (Inter, JetBrains Mono) for snappy first paint,
//   - applies the dark theme class on <html> so SSR renders the right colors.
//
// The dark theme is the ONLY theme — no light-mode toggle. SOC analysts
// work in low-light environments; light mode would be both unfriendly and
// out of keeping with the product identity.
// =============================================================================

import Document, { Html, Head, Main, NextScript } from 'next/document';

class LateDDocument extends Document {
  render() {
    return (
      <Html lang="en" className="dark">
        <Head>
          <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="" />
          <link
            href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;600&display=swap"
            rel="stylesheet"
          />
          <meta name="theme-color" content="#070A12" />
        </Head>
        <body className="bg-canvas text-ink">
          <Main />
          <NextScript />
        </body>
      </Html>
    );
  }
}

export default LateDDocument;
