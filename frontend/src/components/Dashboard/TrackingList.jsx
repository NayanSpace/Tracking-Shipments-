import { useState, useEffect, useCallback } from "react";
import { listTrackingApi, getFriendlyError } from "../../services/api";
import TrackingCard from "./TrackingCard";
import { useToast } from "../../contexts/ToastContext";

const STATUSES = ["", "Pending", "In Transit", "Out for Delivery", "Delivered", "Exception", "Failed"];
const CARRIERS = [
  { value: "", label: "All Carriers" },
  { value: "UPS", label: "UPS" },
  { value: "FEDEX", label: "FedEx" },
  { value: "DAYROSS", label: "Day & Ross" },
  { value: "POLARIS", label: "Polaris" },
];

function SkeletonCard() {
  return (
    <div className="card animate-pulse space-y-3">
      <div className="flex justify-between">
        <div className="space-y-1">
          <div className="h-3 w-12 bg-gray-200 rounded" />
          <div className="h-5 w-40 bg-gray-200 rounded" />
        </div>
        <div className="h-6 w-20 bg-gray-200 rounded-full" />
      </div>
      <div className="h-3 w-32 bg-gray-200 rounded" />
      <div className="h-3 w-24 bg-gray-200 rounded" />
    </div>
  );
}

export default function TrackingList({ refreshSignal }) {
  const [data, setData] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [carrierFilter, setCarrierFilter] = useState("");
  const { addToast } = useToast();

  const fetchData = useCallback(async (showSpinner = false) => {
    if (showSpinner) setLoading(true);
    try {
      const res = await listTrackingApi({
        status_filter: statusFilter || undefined,
        carrier_filter: carrierFilter || undefined,
        search: search || undefined,
      });
      setData(res.data);
      setTotal(res.total);
    } catch (err) {
      addToast(getFriendlyError(err), "error");
    } finally {
      setLoading(false);
    }
  }, [statusFilter, carrierFilter, search]);

  // Initial load and refresh signal
  useEffect(() => {
    fetchData(true);
  }, [fetchData, refreshSignal]);

  // Poll every 30 seconds for live updates
  useEffect(() => {
    const interval = setInterval(() => fetchData(false), 30_000);
    return () => clearInterval(interval);
  }, [fetchData]);

  const handleUpdate = () => fetchData(false);

  return (
    <div>
      {/* Filters */}
      <div className="flex flex-wrap gap-3 mb-6">
        <input
          type="text"
          placeholder="Search tracking number…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="input max-w-xs text-sm"
        />

        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="input w-auto text-sm"
        >
          <option value="">All Statuses</option>
          {STATUSES.filter(Boolean).map((s) => (
            <option key={s} value={s}>{s}</option>
          ))}
        </select>

        <select
          value={carrierFilter}
          onChange={(e) => setCarrierFilter(e.target.value)}
          className="input w-auto text-sm"
        >
          {CARRIERS.map((c) => (
            <option key={c.value} value={c.value}>{c.label}</option>
          ))}
        </select>

        {total > 0 && (
          <span className="text-sm text-gray-500 self-center">
            {total} shipment{total !== 1 ? "s" : ""}
          </span>
        )}
      </div>

      {/* Loading */}
      {loading && (
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {[1, 2, 3].map((i) => <SkeletonCard key={i} />)}
        </div>
      )}

      {/* Empty state */}
      {!loading && data.length === 0 && (
        <div className="text-center py-16 text-gray-500">
          <div className="text-5xl mb-4">📭</div>
          <p className="text-lg font-medium">No shipments found</p>
          <p className="text-sm mt-1">
            {search || statusFilter || carrierFilter
              ? "Try clearing your filters"
              : "Add tracking numbers above to get started"}
          </p>
        </div>
      )}

      {/* Cards grid */}
      {!loading && data.length > 0 && (
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {data.map((item) => (
            <TrackingCard key={item.id} tracking={item} onUpdate={handleUpdate} />
          ))}
        </div>
      )}
    </div>
  );
}
