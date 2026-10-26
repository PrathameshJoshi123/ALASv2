"use client";

import { useEffect, Suspense } from "react";
import { useSearchParams, useRouter } from "next/navigation";

function TenantFilesRedirectContent() {
  const router = useRouter();
  const searchParams = useSearchParams();

  useEffect(() => {
    const id = searchParams.get("id");
    const query = searchParams.toString();
    if (id) {
      router.replace(`/dashboard/drafting/editor/${id}${query ? `?${query}` : ""}`);
    } else {
      router.replace(`/dashboard/drafting${query ? `?${query}` : ""}`);
    }
  }, [router, searchParams]);

  return null;
}

export default function TenantFilesRedirectPage() {
  return (
    <Suspense fallback={null}>
      <TenantFilesRedirectContent />
    </Suspense>
  );
}
