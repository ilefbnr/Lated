// =============================================================================
// pages/index.tsx — landing redirect
// =============================================================================
//
// PURPOSE
// -------
// Redirects "/" to "/overview" — the default SOC operator landing page.
// Keeps URLs stable when the home page changes later (e.g. saved bookmarks
// pointing at "/" survive product reorganizations).
// =============================================================================

import type { GetServerSideProps } from 'next';

export const getServerSideProps: GetServerSideProps = async () => ({
  redirect: { destination: '/overview', permanent: false },
});

export default function IndexPage() {
  return null;
}
