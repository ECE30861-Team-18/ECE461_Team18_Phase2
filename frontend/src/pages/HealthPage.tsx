import React, { useState, useEffect } from "react";
import {
  Box,
  Paper,
  Typography,
  Alert,
  CircularProgress,
  Chip,
  Card,
  CardContent,
  Grid,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  Button,
  FormControlLabel,
  Switch,
  TextField,
} from "@mui/material";
import {
  ExpandMore as ExpandMoreIcon,
  CheckCircle as CheckIcon,
  Warning as WarningIcon,
  Error as ErrorIcon,
  Help as HelpIcon,
  Refresh as RefreshIcon,
} from "@mui/icons-material";
import { HealthComponentCollection, HealthStatus } from "../types";
import apiClient from "../api";

const statusConfig: Record<
  HealthStatus,
  { color: "success" | "warning" | "error" | "default"; icon: React.ReactNode }
> = {
  ok: { color: "success", icon: <CheckIcon /> },
  degraded: { color: "warning", icon: <WarningIcon /> },
  critical: { color: "error", icon: <ErrorIcon /> },
  unknown: { color: "default", icon: <HelpIcon /> },
};

export default function HealthPage() {
  const [healthData, setHealthData] =
    useState<HealthComponentCollection | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [windowMinutes, setWindowMinutes] = useState(60);
  const [includeTimeline, setIncludeTimeline] = useState(false);
  const [systemOk, setSystemOk] = useState(false);

  useEffect(() => {
    checkHealth();
    loadHealthComponents();
  }, []);

  const checkHealth = async () => {
    try {
      await apiClient.healthCheck();
      setSystemOk(true);
    } catch (err) {
      setSystemOk(false);
    }
  };

  const loadHealthComponents = async () => {
    setLoading(true);
    setError("");

    try {
      const data = await apiClient.getHealthComponents(
        windowMinutes,
        includeTimeline
      );
      setHealthData(data);
    } catch (err: any) {
      setError(err.message || "Failed to load health data");
    } finally {
      setLoading(false);
    }
  };

  const handleRefresh = () => {
    checkHealth();
    loadHealthComponents();
  };

  const overallStatus = healthData?.components.reduce<HealthStatus>(
    (worst, component) => {
      const statusPriority = { critical: 3, degraded: 2, ok: 1, unknown: 0 };
      const currentPriority = statusPriority[component.status] || 0;
      const worstPriority = statusPriority[worst] || 0;
      return currentPriority > worstPriority ? component.status : worst;
    },
    "ok"
  );

  if (loading && !healthData) {
    return (
      <Box sx={{ display: "flex", justifyContent: "center", p: 4 }}>
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Box>
      <Box
        sx={{
          mb: 3,
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
        }}
      >
        <Typography variant="h4">System Health</Typography>
        <Button
          startIcon={<RefreshIcon />}
          onClick={handleRefresh}
          disabled={loading}
        >
          Refresh
        </Button>
      </Box>

      {error && (
        <Alert severity="error" sx={{ mb: 3 }}>
          {error}
        </Alert>
      )}

      <Grid container spacing={3} sx={{ mb: 3 }}>
        <Grid size={{ xs: 12, md: 6 }}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                API Status
              </Typography>
              <Box sx={{ display: "flex", alignItems: "center", gap: 2 }}>
                <Chip
                  label={systemOk ? "Online" : "Offline"}
                  color={systemOk ? "success" : "error"}
                  icon={systemOk ? <CheckIcon /> : <ErrorIcon />}
                />
                <Typography variant="body2" color="text.secondary">
                  Heartbeat check
                </Typography>
              </Box>
            </CardContent>
          </Card>
        </Grid>

        <Grid size={{ xs: 12, md: 6 }}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Overall Component Status
              </Typography>
              <Box sx={{ display: "flex", alignItems: "center", gap: 2 }}>
                {overallStatus && (
                  <Chip
                    label={overallStatus.toUpperCase()}
                    color={statusConfig[overallStatus].color}
                    icon={
                      statusConfig[overallStatus].icon as React.ReactElement
                    }
                  />
                )}
                {healthData && (
                  <Typography variant="body2" color="text.secondary">
                    {healthData.components.length} component
                    {healthData.components.length !== 1 ? "s" : ""} monitored
                  </Typography>
                )}
              </Box>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      <Paper sx={{ p: 3, mb: 3 }}>
        <Typography variant="h6" gutterBottom>
          Monitoring Options
        </Typography>
        <Box
          sx={{
            display: "flex",
            gap: 2,
            alignItems: "center",
            flexWrap: "wrap",
          }}
        >
          <TextField
            type="number"
            label="Window (minutes)"
            value={windowMinutes}
            onChange={(e) => setWindowMinutes(parseInt(e.target.value, 10))}
            inputProps={{ min: 5, max: 1440 }}
            sx={{ width: 180 }}
          />
          <FormControlLabel
            control={
              <Switch
                checked={includeTimeline}
                onChange={(e) => setIncludeTimeline(e.target.checked)}
              />
            }
            label="Include timeline"
          />
          <Button
            variant="contained"
            onClick={loadHealthComponents}
            disabled={loading}
          >
            Apply
          </Button>
        </Box>
      </Paper>

      {healthData && (
        <Box>
          <Typography variant="h5" gutterBottom>
            Component Details
          </Typography>
          <Typography variant="body2" color="text.secondary" paragraph>
            Generated at: {new Date(healthData.generated_at).toLocaleString()}
            {healthData.window_minutes &&
              ` (${healthData.window_minutes} min window)`}
          </Typography>

          {healthData.components.map((component) => (
            <Accordion
              key={component.id}
              defaultExpanded={component.status !== "ok"}
            >
              <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                <Box
                  sx={{
                    display: "flex",
                    alignItems: "center",
                    gap: 2,
                    width: "100%",
                  }}
                >
                  <Chip
                    label={component.status.toUpperCase()}
                    color={statusConfig[component.status].color}
                    size="small"
                  />
                  <Typography variant="h6">
                    {component.display_name || component.id}
                  </Typography>
                  {component.issues && component.issues.length > 0 && (
                    <Chip
                      label={`${component.issues.length} issue${
                        component.issues.length !== 1 ? "s" : ""
                      }`}
                      size="small"
                      color="error"
                    />
                  )}
                </Box>
              </AccordionSummary>
              <AccordionDetails>
                <Box>
                  {component.description && (
                    <Typography variant="body2" paragraph>
                      {component.description}
                    </Typography>
                  )}

                  <Typography
                    variant="body2"
                    color="text.secondary"
                    gutterBottom
                  >
                    Last observed:{" "}
                    {new Date(component.observed_at).toLocaleString()}
                  </Typography>

                  {component.metrics &&
                    Object.keys(component.metrics).length > 0 && (
                      <Box sx={{ mt: 2, mb: 2 }}>
                        <Typography variant="subtitle2" gutterBottom>
                          Metrics:
                        </Typography>
                        <Grid container spacing={1}>
                          {Object.entries(component.metrics).map(
                            ([key, value]) => (
                              <Grid size={{ xs: 12, sm: 6, md: 4 }} key={key}>
                                <Card variant="outlined">
                                  <CardContent sx={{ p: 1 }}>
                                    <Typography
                                      variant="caption"
                                      color="text.secondary"
                                    >
                                      {key}
                                    </Typography>
                                    <Typography
                                      variant="body2"
                                      fontWeight="medium"
                                    >
                                      {String(value.value ?? value)}
                                    </Typography>
                                  </CardContent>
                                </Card>
                              </Grid>
                            )
                          )}
                        </Grid>
                      </Box>
                    )}

                  {component.issues && component.issues.length > 0 && (
                    <Box sx={{ mt: 2 }}>
                      <Typography
                        variant="subtitle2"
                        gutterBottom
                        color="error"
                      >
                        Issues:
                      </Typography>
                      {component.issues.map((issue, idx) => (
                        <Alert
                          key={idx}
                          severity={issue.severity}
                          sx={{ mb: 1 }}
                        >
                          <Typography variant="body2" fontWeight="medium">
                            [{issue.code}] {issue.summary}
                          </Typography>
                          {issue.details && (
                            <Typography variant="body2" sx={{ mt: 0.5 }}>
                              {issue.details}
                            </Typography>
                          )}
                        </Alert>
                      ))}
                    </Box>
                  )}

                  {component.timeline && component.timeline.length > 0 && (
                    <Box sx={{ mt: 2 }}>
                      <Typography variant="subtitle2" gutterBottom>
                        Activity Timeline:
                      </Typography>
                      <Box sx={{ display: "flex", gap: 1, flexWrap: "wrap" }}>
                        {component.timeline.map((entry, idx) => (
                          <Chip
                            key={idx}
                            label={`${entry.value} ${entry.unit || ""}`}
                            size="small"
                            variant="outlined"
                          />
                        ))}
                      </Box>
                    </Box>
                  )}

                  {component.logs && component.logs.length > 0 && (
                    <Box sx={{ mt: 2 }}>
                      <Typography variant="subtitle2" gutterBottom>
                        Log References:
                      </Typography>
                      {component.logs.map((log, idx) => (
                        <Box key={idx} sx={{ mb: 1 }}>
                          <Typography variant="body2">
                            {log.label}{" "}
                            <a
                              href={log.url}
                              target="_blank"
                              rel="noopener noreferrer"
                            >
                              View
                            </a>
                          </Typography>
                        </Box>
                      ))}
                    </Box>
                  )}
                </Box>
              </AccordionDetails>
            </Accordion>
          ))}
        </Box>
      )}
    </Box>
  );
}
