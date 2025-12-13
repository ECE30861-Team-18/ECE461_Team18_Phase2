import React, { useState } from "react";

export default function Ingest() {
  const [modelUrl, setModelUrl] = useState("");

  const handleSubmit = (e) => {
    e.preventDefault();
    console.log("Submitting model for ingestion:", modelUrl);

    // In the future, you can call your create_artifact API here.
    // For now, just clear the field.
    setModelUrl("");
  };

  return (
    <div style={{ 
      display: "flex", 
      flexDirection: "column", 
      alignItems: "center", 
      justifyContent: "center", 
      height: "100vh" 
    }}>
      <h2 style={{ marginBottom: "20px" }}>Ingest New Model</h2>
      <form 
        onSubmit={handleSubmit} 
        style={{ display: "flex", alignItems: "center", gap: "10px" }}
      >
        <input
          type="text"
          placeholder="Enter Hugging Face model URL"
          value={modelUrl}
          onChange={(e) => setModelUrl(e.target.value)}
          style={{
            width: "400px",
            padding: "10px",
            fontSize: "16px",
            borderRadius: "8px",
            border: "1px solid #ccc",
          }}
        />
        <button
          type="submit"
          style={{
            padding: "10px 18px",
            borderRadius: "8px",
            backgroundColor: "#007bff",
            color: "white",
            border: "none",
            cursor: "pointer",
          }}
        >
          Submit
        </button>
      </form>
    </div>
  );
}
