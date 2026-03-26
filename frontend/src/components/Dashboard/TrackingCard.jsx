import { useState } from "react";
import { refreshTrackingApi, deleteTrackingApi, getFriendlyError } from "../../services/api";
import { useToast } from "../../contexts/ToastContext";

const STATUS_STYLES = {
  Delivered: "bg-success-500",
  "In Transit": "bg-primary-500",
  "Out for Delivery": "bg-warning-500",
  Exception: "bg-error-500",
  Pending: "bg-gray-400",
  Failed: "bg-error-700",
};

const CARRIER_LABELS = {
  UPS: "UPS",
  FEDEX: "FedEx",
  DAYROSS: "Day & Ross",
  POLARIS: "Polaris",
};

function getRelativeTime(date) {
  if (!date) return "never";
  const seconds = Math.floor((Date.now() - new Date(date)) / 1000);
  if (seconds < 60) return "just now";
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
  return `${Math.floor(seconds / 86400)}d ago`;
}

function getDaysUntil(date) {
  if (!date) return null;
  const ms = new Date(date) - Date.now();
  return Math.ceil(ms / (1000 * 60 * 60 * 24));
}

export default function TrackingCard({ tracking, onUpdate }) {
  const [expanded, setExpanded] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const { addToast } = useToast();

  const handleRefresh = async () => {
    setRefreshing(true);
    try {
      await refreshTrackingApi(tracking.id);
      addToast("Refresh queued — update will appear shortly", "info");
      // Poll once after 4 seconds to pick up the update
      setTimeout(onUpdate, 4000);
    } catch (err) {
      addToast(getFriendlyError(err), "error");
    } finally {
      setRefreshing(false);
    }
  };

  const handleDelete = async () => {
    try {
      await deleteTrackingApi(tracking.id);
      addToast("Tracking removed", "success");
      onUpdate();
    } catch (err) {
      addToast(getFriendlyError(err), "error");
    } finally {
      setConfirmDelete(false);
    }
  };

  const statusColor = STATUS_STYLES[tracking.status] ?? "bg-gray-400";
  const daysLeft = getDaysUntil(tracking.delete_at);

  return (
    <div className="card flex flex-col gap-3 relative">
      {/* Header row */}
      <div className="flex justify-between items-start gap-2">
        <div className="min-w-0">
          <p className="text-xs font-medium text-gray-500 uppercase tracking-wide">
            {CARRIER_LABELS[tracking.carrier] ?? tracking.carrier}
          </p>
          <p className="font-mono font-semibold text-gray-900 truncate">
            {tracking.tracking_number}
          </p>
        </div>
        <span className={`${statusColor} text-white text-xs font-medium px-2.5 py-1 rounded-full whitespace-nowrap flex-shrink-0`}>
          {tracking.status}
        </span>
      </div>

      {/* Location */}
      {tracking.current_location && (
        <div>
          <p className="text-xs text-gray-500">📍 Current Location</p>
          <p className="text-sm font-medium text-gray-800">{tracking.current_location}</p>
        </div>
      )}

      {/* Delivery date */}
      {(tracking.estimated_delivery || tracking.delivered_date) && (
        <div>
          <p className="text-xs text-gray-500">
            {tracking.status === "Delivered" ? "✓ Delivered" : "📅 Estimated Delivery"}
          </p>
          <p className="text-sm font-medium text-gray-800">
            {new Date(tracking.delivered_date ?? tracking.estimated_delivery).toLocaleDateString(
              "en-CA", { year: "numeric", month: "short", day: "numeric" }
            )}
          </p>
        </div>
      )}

      {/* Error message */}
      {tracking.error_message && (
        <div className="bg-error-50 border border-error-200 rounded-md px-3 py-2">
          <p className="text-xs text-error-700">{tracking.error_message}</p>
        </div>
      )}

      {/* Timeline toggle */}
      {tracking.events?.length > 0 && (
        <button
          onClick={() => setExpanded((v) => !v)}
          className="text-primary-500 text-xs hover:underline text-left"
        >
          {expanded ? "Hide" : "Show"} timeline ({tracking.events.length} events)
        </button>
      )}

      {/* Timeline */}
      {expanded && tracking.events?.length > 0 && (
        <div className="border-t pt-3 space-y-3 max-h-64 overflow-y-auto">
          {tracking.events.map((ev, i) => (
            <div key={i} className="flex gap-3">
              <div className="flex-shrink-0 mt-1.5">
                <div className="w-2 h-2 rounded-full bg-primary-500" />
              </div>
              <div>
                <p className="text-xs font-medium text-gray-800">{ev.status}</p>
                {ev.location && <p className="text-xs text-gray-500">{ev.location}</p>}
                <p className="text-xs text-gray-400">
                  {new Date(ev.timestamp).toLocaleString("en-CA", {
                    dateStyle: "medium", timeStyle: "short",
                  })}
                </p>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Auto-delete countdown */}
      {daysLeft !== null && daysLeft > 0 && (
        <div className="bg-gray-50 rounded-md px-3 py-1.5 text-xs text-gray-500">
          ⏱ Auto-removes in {daysLeft} day{daysLeft !== 1 ? "s" : ""}
        </div>
      )}

      {/* Footer: last updated + actions */}
      <div className="flex justify-between items-center border-t pt-3 mt-auto">
        <p className="text-xs text-gray-400">Updated {getRelativeTime(tracking.last_updated)}</p>

        <div className="flex items-center gap-1">
          {/* Refresh */}
          <button
            onClick={handleRefresh}
            disabled={refreshing}
            title="Refresh now"
            className="p-1.5 text-gray-500 hover:text-primary-500 hover:bg-primary-50 rounded transition-colors disabled:opacity-40"
          >
            <svg className={`w-4 h-4 ${refreshing ? "animate-spin" : ""}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
          </button>

          {/* Delete */}
          {!confirmDelete ? (
            <button
              onClick={() => setConfirmDelete(true)}
              title="Remove"
              className="p-1.5 text-gray-500 hover:text-error-500 hover:bg-error-50 rounded transition-colors"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
              </svg>
            </button>
          ) : (
            <div className="flex items-center gap-1">
              <button onClick={handleDelete} className="text-xs text-error-600 font-medium hover:underline">
                Confirm
              </button>
              <button onClick={() => setConfirmDelete(false)} className="text-xs text-gray-500 hover:underline">
                Cancel
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
