import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Box,
  Grid,
  Card,
  CardContent,
  Typography,
  Button,
  Alert,
  CircularProgress,
  Chip,
  Paper,
  List,
  ListItemText,
  ListItemButton,
} from '@mui/material';
import InventoryIcon from '@mui/icons-material/Inventory';
import AddIcon from '@mui/icons-material/Add';
import TrendingUpIcon from '@mui/icons-material/TrendingUp';
import CloudIcon from '@mui/icons-material/CloudDone';
import { ArtifactMetadata } from '../types';
import apiClient from '../api';
import { useAuth } from '../AuthContext';

export default function DashboardPage() {
  const navigate = useNavigate();
  const { user } = useAuth();

  const [recentArtifacts, setRecentArtifacts] = useState<ArtifactMetadata[]>([]);
  // const [tracks, setTracks] = useState<TracksResponse | null>(null);
  const [stats, setStats] = useState({
    total: 0,
    models: 0,
    datasets: 0,
    code: 0,
  });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    loadDashboardData();
  }, []);

  const loadDashboardData = async () => {
    setLoading(true);
    setError('');

    try {
      // Load all artifacts
      const response = await apiClient.listArtifacts([{ name: '*' }]);
      const artifacts = response.data;

      // Calculate stats
      setStats({
        total: artifacts.length,
        models: artifacts.filter((a) => a.type === 'model').length,
        datasets: artifacts.filter((a) => a.type === 'dataset').length,
        code: artifacts.filter((a) => a.type === 'code').length,
      });
      // Show recent 5 artifacts
      setRecentArtifacts(artifacts.slice(0, 5));

      // Load tracks information
      // try {
      //   const tracksData = await apiClient.getTracks();
      //   setTracks(tracksData);
      // } catch (err) {
      //   console.warn('Tracks not available:', err);
      // }
    } catch (err: any) {
      setError(err.message || 'Failed to load dashboard data');
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}>
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Box>
      <Box sx={{ mb: 4 }}>
        <Typography variant="h4" gutterBottom>
          Welcome back, {user?.name || 'User'}!
        </Typography>
        <Typography variant="body1" color="text.secondary">
          ECE 461 Fall 2025 - Trustworthy Model Registry Dashboard
        </Typography>
      </Box>

      {error && (
        <Alert severity="error" sx={{ mb: 3 }}>
          {error}
        </Alert>
      )}

      <Grid container spacing={3} sx={{ mb: 4 }}>
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <Card>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                <InventoryIcon color="primary" sx={{ mr: 1 }} />
                <Typography color="text.secondary" variant="body2">
                  Total Artifacts
                </Typography>
              </Box>
              <Typography variant="h3">{stats.total}</Typography>
            </CardContent>
          </Card>
        </Grid>

        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <Card>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                <TrendingUpIcon color="primary" sx={{ mr: 1 }} />
                <Typography color="text.secondary" variant="body2">
                  Models
                </Typography>
              </Box>
              <Typography variant="h3">{stats.models}</Typography>
            </CardContent>
          </Card>
        </Grid>

        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <Card>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                <CloudIcon color="success" sx={{ mr: 1 }} />
                <Typography color="text.secondary" variant="body2">
                  Datasets
                </Typography>
              </Box>
              <Typography variant="h3">{stats.datasets}</Typography>
            </CardContent>
          </Card>
        </Grid>

        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <Card>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                <AddIcon color="warning" sx={{ mr: 1 }} />
                <Typography color="text.secondary" variant="body2">
                  Code
                </Typography>
              </Box>
              <Typography variant="h3">{stats.code}</Typography>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      <Grid container spacing={3}>
        <Grid size={{ xs: 12, md: 8 }}> 
          <Paper sx={{ p: 3 }}>
            <Typography variant="h6" gutterBottom>
              Recent Artifacts
            </Typography>
            {recentArtifacts.length > 0 ? (
              <List>
                {recentArtifacts.map((artifact) => (
                  <ListItemButton
                    key={artifact.id}
                    onClick={() =>
                      navigate(`/artifacts/${artifact.type}/${artifact.id}`)
                    }
                  >
                    <ListItemText
                      primary={artifact.name}
                      secondary={`ID: ${artifact.id}`}
                    />
                    <Chip label={artifact.type} size="small" />
                  </ListItemButton>
                ))}
              </List>
            ) : (
              <Typography variant="body2" color="text.secondary">
                No artifacts yet. Create your first one!
              </Typography>
            )}
            <Box sx={{ mt: 2, display: 'flex', gap: 2 }}>
              <Button
                variant="outlined"
                fullWidth
                onClick={() => navigate('/artifacts')}
              >
                View All Artifacts
              </Button>
              <Button
                variant="contained"
                fullWidth
                onClick={() => navigate('/artifacts/create')}
              >
                Create New
              </Button>
            </Box>
          </Paper>
        </Grid>

        <Grid size={{ xs: 12, md: 4 }}>
          <Paper sx={{ p: 3, mb: 3 }}>
            <Typography variant="h6" gutterBottom>
              Quick Actions
            </Typography>
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
              <Button
                variant="contained"
                startIcon={<AddIcon />}
                onClick={() => navigate('/artifacts/create')}
              >
                Create Artifact
              </Button>
              <Button
                variant="outlined"
                startIcon={<InventoryIcon />}
                onClick={() => navigate('/artifacts')}
              >
                Browse Artifacts
              </Button>
              <Button
                variant="outlined"
                startIcon={<CloudIcon />}
                onClick={() => navigate('/health')}
              >
                System Health
              </Button>
            </Box>
          </Paper>

          {/* {tracks && tracks.plannedTracks.length > 0 && (
            <Paper sx={{ p: 3 }}>
              <Typography variant="h6" gutterBottom>
                Implementation Tracks
              </Typography>
              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                {tracks.plannedTracks.map((track, idx) => (
                  <Chip key={idx} label={track} color="primary" variant="outlined" />
                ))}
              </Box>
            </Paper>
          )} */}
        </Grid>
      </Grid>
    </Box>
  );
}