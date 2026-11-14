import { Suspense } from "react";

import { Spinner } from "@/components/ui";

import InterviewSession from "./InterviewSession";

export default function InterviewPage() {
  return (
    <Suspense fallback={<Spinner />}>
      <InterviewSession />
    </Suspense>
  );
}
