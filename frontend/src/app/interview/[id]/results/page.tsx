import { Suspense } from "react";

import { Spinner } from "@/components/ui";

import Results from "./Results";

export default function ResultsPage() {
  return (
    <Suspense fallback={<Spinner />}>
      <Results />
    </Suspense>
  );
}
