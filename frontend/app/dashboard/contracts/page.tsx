"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

export default function ContractsRedirectPage() {
  const router = useRouter();

  useEffect(() => {
    router.replace("/dashboard/analysis");
  }, [router]);

  return null;
}
