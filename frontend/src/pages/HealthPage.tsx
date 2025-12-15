import { useState, useEffect } from 'react';
import {
  Box,
  Typography,
  Button,
  Chip,
  Card,
  CardContent,
  Grid,
} from '@mui/material';
import {
  CheckCircle as CheckIcon,
  Error as ErrorIcon,
  Refresh as RefreshIcon,
} from '@mui/icons-material';
import apiClient from '../api';

export default function HealthPage() {
  const [systemOk, setSystemOk] = useState(false);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    checkHealth();
  }, []);

  const checkHealth = async () => {
    setLoading(true);
    try {
      await apiClient.healthCheck();
      setSystemOk(true);
    } catch (err) {
      setSystemOk(false);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Box>
      <Box
        sx={{
          mb: 3,
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
        }}
      >
        <Typography variant="h4">System Health</Typography>
        <Button
          startIcon={<RefreshIcon />}
          onClick={checkHealth}
          disabled={loading}
        >
          Refresh
        </Button>
      </Box>

      <Grid container spacing={3}>
        <Grid size={{ xs: 12, md: 6 }}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                API Status
              </Typography>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                <Chip
                  label={systemOk ? 'Online' : 'Offline'}
                  color={systemOk ? 'success' : 'error'}
                  icon={systemOk ? <CheckIcon /> : <ErrorIcon />}
                />
                <Typography variant="body2" color="text.secondary">
                  Heartbeat check
                </Typography>
              </Box>
            </CardContent>
          </Card>
        </Grid>
      </Grid>
    </Box>
  );
}