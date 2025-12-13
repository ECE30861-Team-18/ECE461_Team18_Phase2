import { useEffect, useState } from "react";
import { healthCheck } from "../api/client";
import { Alert, CircularProgress, Box } from "@mui/material";

function HealthStatus() {
  const [status, setStatus] = useState("loading");
  const [error, setError] = useState(null);

  useEffect(() => {
    healthCheck()
      .then(() => setStatus("ok"))
      .catch((err) => {
        setStatus("error");
        setError(err.message);
      });
  }, []);

  if (status === "loading") {
    return <CircularProgress aria-label="Loading system health status" />;
  }

  if (status === "error") {
    return (
      <Alert severity="error">
        Backend unavailable: {error}
      </Alert>
    );
  }

  return (
    <Alert severity="success">
      Backend is healthy
    </Alert>
  );
}

export default HealthStatus;
