import { useState } from "react";
import { addTrackingApi, getFriendlyError } from "../../services/api";
import { detectCarrier } from "../../utils/auth";
import { useToast } from "../../contexts/ToastContext";

const CARRIERS = [
  { value: "UPS", label: "UPS" },
  { value: "FEDEX", label: "FedEx" },
  { value: "DAYROSS", label: "Day & Ross" },
  { value: "POLARIS", label: "Polaris Transportation" },
];

export default function TrackingForm({ onSuccess }) {
  const [carrier, setCarrier] = useState("UPS");
  const [trackingNumbers, setTrackingNumbers] = useState("");
  const [loading, setLoading] = useState(false);
  const { addToast } = useToast();

  // Auto-detect carrier when pasting a single tracking number
  const handleTrackingChange = (e) => {
    const val = e.target.value;
    setTrackingNumbers(val);
    const lines = val.split("\n").map((l) => l.trim()).filter(Boolean);
    if (lines.length === 1) {
      const detected = detectCarrier(lines[0]);
      if (detected) setCarrier(detected);
    }
  };

  const parsedNumbers = trackingNumbers
    .split("\n")
    .map((n) => n.trim())
    .filter((n) => n.length > 0);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (parsedNumbers.length === 0) {
      addToast("Enter at least one tracking number", "warning");
      return;
    }

    setLoading(true);
    try {
      await addTrackingApi(carrier, parsedNumbers);
      addToast(
        `Added ${parsedNumbers.length} tracking number${parsedNumbers.length !== 1 ? "s" : ""}. Scraping in progress…`,
        "success"
      );
      setTrackingNumbers("");
      onSuccess?.();
    } catch (err) {
      addToast(getFriendlyError(err), "error");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="card mb-6">
      <h2 className="text-lg font-semibold text-gray-900 mb-4">Add Tracking Numbers</h2>

      <form onSubmit={handleSubmit}>
        <div className="grid sm:grid-cols-4 gap-4 mb-4">
          {/* Carrier select */}
          <div className="sm:col-span-1">
            <label className="label" htmlFor="carrier">Carrier</label>
            <select
              id="carrier"
              value={carrier}
              onChange={(e) => setCarrier(e.target.value)}
              className="input"
            >
              {CARRIERS.map((c) => (
                <option key={c.value} value={c.value}>
                  {c.label}
                </option>
              ))}
            </select>
          </div>

          {/* Tracking numbers textarea */}
          <div className="sm:col-span-3">
            <label className="label" htmlFor="tracking">
              Tracking Numbers (one per line)
              {parsedNumbers.length > 0 && (
                <span className="text-gray-400 font-normal ml-1">
                  — {parsedNumbers.length} number{parsedNumbers.length !== 1 ? "s" : ""}
                </span>
              )}
            </label>
            <textarea
              id="tracking"
              value={trackingNumbers}
              onChange={handleTrackingChange}
              className="input resize-none font-mono text-sm"
              rows={3}
              placeholder={"1Z999AA10123456784\n1Z999AA10123456785"}
              required
            />
            <p className="text-xs text-gray-400 mt-1">
              Tip: paste a UPS or FedEx number and the carrier will be auto-detected.
            </p>
          </div>
        </div>

        <button type="submit" disabled={loading} className="btn btn-primary">
          {loading ? "Adding…" : "Add Tracking"}
        </button>
      </form>
    </div>
  );
}
