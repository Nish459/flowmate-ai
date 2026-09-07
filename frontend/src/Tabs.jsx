import { useState } from "react";

export default function Tabs({ tabs, defaultTab, active: controlledActive, onChange }) {
  const [internalActive, setInternalActive] = useState(defaultTab ?? tabs[0].key);
  const active = controlledActive ?? internalActive;
  const activeTab = tabs.find((t) => t.key === active) ?? tabs[0];

  function selectTab(key) {
    if (controlledActive === undefined) setInternalActive(key);
    onChange?.(key);
  }

  return (
    <div className="tabs">
      <div className="tabs-bar" role="tablist">
        {tabs.map((tab) => (
          <button
            key={tab.key}
            type="button"
            role="tab"
            aria-selected={tab.key === active}
            className={`tab-button ${tab.key === active ? "tab-active" : ""}`}
            onClick={() => selectTab(tab.key)}
          >
            {tab.label}
          </button>
        ))}
      </div>
      <div className="tab-panel" key={activeTab.key}>
        {activeTab.render()}
      </div>
    </div>
  );
}
