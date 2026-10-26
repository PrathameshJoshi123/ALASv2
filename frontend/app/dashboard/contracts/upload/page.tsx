"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

export default function ContractsUploadRedirectPage() {
  const router = useRouter();

  useEffect(() => {
    router.replace("/dashboard/analysis/upload");
  }, [router]);

  return null;
}
