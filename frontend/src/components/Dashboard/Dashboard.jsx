import { useState } from "react";
import Header from "../Layout/Header";
import TrackingForm from "./TrackingForm";
import TrackingList from "./TrackingList";

export default function Dashboard() {
  const [refreshSignal, setRefreshSignal] = useState(0);

  const handleTrackingAdded = () => {
    // Bump the signal to trigger TrackingList to re-fetch
    setRefreshSignal((n) => n + 1);
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <Header />

      <main className="max-w-7xl mx-auto px-4 sm:px-6 py-8">
        <TrackingForm onSuccess={handleTrackingAdded} />
        <TrackingList refreshSignal={refreshSignal} />
      </main>
    </div>
  );
}
