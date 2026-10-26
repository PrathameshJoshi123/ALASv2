"use client";

import { useEffect } from "react";
import { useParams, useRouter } from "next/navigation";

export default function ContractRedirectPage() {
  const params = useParams();
  const router = useRouter();

  useEffect(() => {
    if (params?.id) {
      router.replace(`/dashboard/analysis/${params.id}`);
    } else {
      router.replace("/dashboard/analysis");
    }
  }, [params, router]);

  return null;
}
