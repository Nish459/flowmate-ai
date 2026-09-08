import { useEffect, useState } from "react";
import { generatePersonalStandup, getEngineers } from "./api";
import Markdown from "./Markdown";

export default function PersonalStandup() {
  const [engineers, setEngineers] = useState(null);
  const [engineersError, setEngineersError] = useState(null);
  const [engineer, setEngineer] = useState("");
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    getEngineers()
      .then(setEngineers)
      .catch((err) => setEngineersError(err.message));
  }, []);

  async function handleGenerate(force) {
    if (!engineer) return;
    setLoading(true);
    setError(null);
    try {
      setResult(await generatePersonalStandup(engineer, force));
    } catch (err) {
      console.error("generatePersonalStandup failed:", err);
      setError("Failed to fetch");
    } finally {
      setLoading(false);
    }
  }

  function handleEngineerChange(e) {
    setEngineer(e.target.value);
    setResult(null);
    setError(null);
  }

  return (
    <div className="personal-standup">
      <h3 className="personal-standup-title">Generate My Standup</h3>
      <div className="standup-form">
        <select value={engineer} onChange={handleEngineerChange} required disabled={!engineers}>
          <option value="" disabled>
            {engineers ? "Select engineer" : "Loading engineers..."}
          </option>
          {engineers?.map((name) => (
            <option key={name} value={name}>
              {name}
            </option>
          ))}
        </select>
        <button type="button" onClick={() => handleGenerate(false)} disabled={loading || !engineer}>
          {loading ? "Generating..." : "Generate My Standup"}
        </button>
      </div>

      {engineersError && <p className="error-text">Could not load engineer list: {engineersError}</p>}
      {error && <p className="error-text">{error}</p>}

      {result && (
        <div className="personal-standup-result">
          <Markdown text={result.text} />
          <button
            type="button"
            className="personal-standup-regenerate"
            onClick={() => handleGenerate(true)}
            disabled={loading}
          >
            {loading ? "Regenerating..." : "Regenerate"}
          </button>
        </div>
      )}
    </div>
  );
}
