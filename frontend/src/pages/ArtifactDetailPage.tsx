import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Box,
  Paper,
  Typography,
  Button,
  Chip,
  Grid,
  Card,
  CardContent,
  Alert,
  CircularProgress,
  Tabs,
  Tab,
  Divider,
  Link,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
} from '@mui/material';
import {
  ArrowBack as BackIcon,
  Delete as DeleteIcon,
  Download as DownloadIcon,
  Assessment as RatingIcon,
  AccountTree as LineageIcon,
  AttachMoney as CostIcon,
  History as AuditIcon,
  Gavel as LicenseIcon,
} from '@mui/icons-material';
import {
  Artifact,
  ArtifactType,
  ModelRating,
  ArtifactLineageGraph,
  ArtifactCost,
} from '../types';
import apiClient from '../api';

interface TabPanelProps {
  children?: React.ReactNode;
  index: number;
  value: number;
}

function TabPanel(props: TabPanelProps) {
  const { children, value, index, ...other } = props;
  return (
    <div
      role="tabpanel"
      hidden={value !== index}
      id={`tabpanel-${index}`}
      aria-labelledby={`tab-${index}`}
      {...other}
    >
      {value === index && <Box sx={{ p: 3 }}>{children}</Box>}
    </div>
  );
}

export default function ArtifactDetailPage() {
  const { type, id } = useParams<{ type: ArtifactType; id: string }>();
  const navigate = useNavigate();

  const [artifact, setArtifact] = useState<Artifact | null>(null);
  const [rating, setRating] = useState<ModelRating | null>(null);
  const [lineage, setLineage] = useState<ArtifactLineageGraph | null>(null);
  const [cost, setCost] = useState<ArtifactCost | null>(null);
  //const [audit, setAudit] = useState<ArtifactAuditEntry[]>([]);
  
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [tabValue, setTabValue] = useState(0);
  
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  //const [licenseDialogOpen, setLicenseDialogOpen] = useState(false);
  const [githubUrl, setGithubUrl] = useState('');
  const [licenseResult, setLicenseResult] = useState<boolean | null>(null);

  useEffect(() => {
    if (type && id) {
      loadArtifactData();
    }
  }, [type, id]);

  const loadArtifactData = async () => {
    if (!type || !id) return;

    setLoading(true);
    setError('');

    try {
      // Load basic artifact data
      const artifactData = await apiClient.getArtifact(type, id);
      setArtifact(artifactData);

      // Load additional data based on type
      if (type === 'model') {
        try {
          const ratingData = await apiClient.getModelRating(id);
          setRating(ratingData);
        } catch (err) {
          console.warn('Rating not available:', err);
        }

        try {
          const lineageData = await apiClient.getModelLineage(id);
          setLineage(lineageData);
        } catch (err) {
          console.warn('Lineage not available:', err);
        }
      }

      // Load cost
      try {
        const costData = await apiClient.getArtifactCost(type, id, true);
        setCost(costData);
      } catch (err) {
        console.warn('Cost not available:', err);
      }

      // // Load audit trail
      // try {
      //   const auditData = await apiClient.getArtifactAudit(type, id);
      //   setAudit(auditData);
      // } catch (err) {
      //   console.warn('Audit trail not available:', err);
      // }
    } catch (err: any) {
      setError(err.message || 'Failed to load artifact');
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async () => {
    if (!type || !id) return;

    try {
      await apiClient.deleteArtifact(type, id);
      navigate('/artifacts');
    } catch (err: any) {
      setError(err.message || 'Failed to delete artifact');
    }
    setDeleteDialogOpen(false);
  };

  const handleLicenseCheck = async () => {
    if (!id || !githubUrl) return;

    try {
      const result = await apiClient.checkModelLicense(id, { github_url: githubUrl });
      setLicenseResult(result);
    } catch (err: any) {
      setError(err.message || 'License check failed');
    }
  };

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}>
        <CircularProgress />
      </Box>
    );
  }

  if (error || !artifact) {
    return (
      <Box>
        <Button startIcon={<BackIcon />} onClick={() => navigate('/artifacts')}>
          Back to Artifacts
        </Button>
        <Alert severity="error" sx={{ mt: 2 }}>
          {error || 'Artifact not found'}
        </Alert>
      </Box>
    );
  }

  return (
    <Box>
      <Box sx={{ mb: 3, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Button startIcon={<BackIcon />} onClick={() => navigate('/artifacts')}>
          Back to Artifacts
        </Button>
        <Box>
          {artifact.data.download_url && (
            <Button
              variant="outlined"
              startIcon={<DownloadIcon />}
              href={artifact.data.download_url}
              sx={{ mr: 1 }}
            >
              Download
            </Button>
          )}
          <Button
            variant="outlined"
            color="error"
            startIcon={<DeleteIcon />}
            onClick={() => setDeleteDialogOpen(true)}
          >
            Delete
          </Button>
        </Box>
      </Box>

      <Paper sx={{ p: 3, mb: 3 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 2 }}>
          <Typography variant="h4">{artifact.metadata.name}</Typography>
          <Chip label={artifact.metadata.type} color="primary" />
        </Box>
        <Typography variant="body2" color="text.secondary" gutterBottom>
          ID: {artifact.metadata.id}
        </Typography>
        <Divider sx={{ my: 2 }} />
        <Typography variant="body1">
          <strong>Source URL:</strong>{' '}
          <Link href={artifact.data.url} target="_blank" rel="noopener">
            {artifact.data.url}
          </Link>
        </Typography>
      </Paper>

      <Paper sx={{ width: '100%' }}>
        <Tabs value={tabValue} onChange={(_, v) => setTabValue(v)}>
          {type === 'model' && <Tab label="Rating" icon={<RatingIcon />} iconPosition="start" />}
          {type === 'model' && <Tab label="Lineage" icon={<LineageIcon />} iconPosition="start" />}
          <Tab label="Cost" icon={<CostIcon />} iconPosition="start" />
          <Tab label="Audit Trail" icon={<AuditIcon />} iconPosition="start" />
          {type === 'model' && <Tab label="License Check" icon={<LicenseIcon />} iconPosition="start" />}
        </Tabs>

        {type === 'model' && (
          <TabPanel value={tabValue} index={0}>
            {rating ? (
              <Grid container spacing={2}>
                <Grid size={{ xs: 12 }}>
                  <Typography variant="h6" gutterBottom>
                    Overall Score: {rating.net_score.toFixed(2)}
                  </Typography>
                </Grid>
                {Object.entries(rating)
                  .filter(([key]) => !key.includes('latency') && key !== 'name' && key !== 'category' && key !== 'size_score')
                  .map(([key, value]) => (
                    <Grid size={{ xs: 12, sm: 6, md: 4 }} key={key}>
                      <Card variant="outlined">
                        <CardContent>
                          <Typography color="text.secondary" gutterBottom>
                            {key.replace(/_/g, ' ').toUpperCase()}
                          </Typography>
                          <Typography variant="h5">
                            {typeof value === 'number' ? value.toFixed(2) : value}
                          </Typography>
                        </CardContent>
                      </Card>
                    </Grid>
                  ))}
                {rating.size_score && (
                  <>
                    <Grid size={{ xs : 12 }}>
                      <Typography variant="h6" gutterBottom sx={{ mt: 2 }}>
                        Size Scores by Platform
                      </Typography>
                    </Grid>
                    {Object.entries(rating.size_score).map(([platform, score]) => (
                      <Grid size={{ xs : 12, sm : 6, md: 3}}>
                        <Card variant="outlined">
                          <CardContent>
                            <Typography color="text.secondary" gutterBottom>
                              {platform.replace(/_/g, ' ').toUpperCase()}
                            </Typography>
                            <Typography variant="h5">{score.toFixed(2)}</Typography>
                          </CardContent>
                        </Card>
                      </Grid>
                    ))}
                  </>
                )}
              </Grid>
            ) : (
              <Alert severity="info">Rating data not available</Alert>
            )}
          </TabPanel>
        )}

        {type === 'model' && (
          <TabPanel value={tabValue} index={1}>
            {lineage ? (
              <Box>
                <Typography variant="h6" gutterBottom>
                  Dependencies & Lineage
                </Typography>
                <Typography variant="body2" paragraph>
                  Nodes: {lineage.nodes.length}, Edges: {lineage.edges.length}
                </Typography>
                
                <Typography variant="subtitle1" gutterBottom sx={{ mt: 2 }}>
                  Nodes:
                </Typography>
                {lineage.nodes.map((node) => (
                  <Card key={node.artifact_id} variant="outlined" sx={{ mb: 1 }}>
                    <CardContent>
                      <Typography variant="body1" fontWeight="medium">
                        {node.name}
                      </Typography>
                      <Typography variant="body2" color="text.secondary">
                        ID: {node.artifact_id} | Source: {node.source}
                      </Typography>
                    </CardContent>
                  </Card>
                ))}

                <Typography variant="subtitle1" gutterBottom sx={{ mt: 3 }}>
                  Relationships:
                </Typography>
                {lineage.edges.map((edge, idx) => (
                  <Typography key={idx} variant="body2" sx={{ mb: 0.5 }}>
                    {edge.from_node_artifact_id} → {edge.to_node_artifact_id} ({edge.relationship})
                  </Typography>
                ))}
              </Box>
            ) : (
              <Alert severity="info">Lineage data not available</Alert>
            )}
          </TabPanel>
        )}

        <TabPanel value={tabValue} index={type === 'model' ? 2 : 0}>
          {cost ? (
            <Box>
              <Typography variant="h6" gutterBottom>
                Cost Analysis (MB)
              </Typography>
              {Object.entries(cost).map(([artifactId, details]) => (
                <Card key={artifactId} variant="outlined" sx={{ mb: 2 }}>
                  <CardContent>
                    <Typography variant="subtitle1" gutterBottom>
                      Artifact ID: {artifactId}
                    </Typography>
                    {details.standalone_cost !== undefined && (
                      <Typography variant="body2">
                        Standalone Cost: {details.standalone_cost.toFixed(2)} MB
                      </Typography>
                    )}
                    <Typography variant="body2">
                      Total Cost: {details.total_cost.toFixed(2)} MB
                    </Typography>
                  </CardContent>
                </Card>
              ))}
            </Box>
          ) : (
            <Alert severity="info">Cost data not available</Alert>
          )}
        </TabPanel>

        {/* <TabPanel value={tabValue} index={type === 'model' ? 3 : 1}>
          {audit.length > 0 ? (
            <Box>
              <Typography variant="h6" gutterBottom>
                Audit History
              </Typography>
              {audit.map((entry, idx) => (
                <Card key={idx} variant="outlined" sx={{ mb: 2 }}>
                  <CardContent>
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                      <Chip label={entry.action} size="small" />
                      <Typography variant="caption" color="text.secondary">
                        {new Date(entry.date).toLocaleString()}
                      </Typography>
                    </Box>
                    <Typography variant="body2">
                      User: {entry.user.name} {entry.user.is_admin && '(Admin)'}
                    </Typography>
                  </CardContent>
                </Card>
              ))}
            </Box>
          ) : (
            <Alert severity="info">No audit history available</Alert>
          )}
        </TabPanel> */}

        {type === 'model' && (
          <TabPanel value={tabValue} index={4}>
            <Typography variant="h6" gutterBottom>
              License Compatibility Check
            </Typography>
            <Box sx={{ display: 'flex', gap: 2, mb: 2 }}>
              <TextField
                fullWidth
                label="GitHub Repository URL"
                placeholder="https://github.com/username/repo"
                value={githubUrl}
                onChange={(e) => setGithubUrl(e.target.value)}
              />
              <Button
                variant="contained"
                onClick={handleLicenseCheck}
                disabled={!githubUrl}
              >
                Check
              </Button>
            </Box>
            {licenseResult !== null && (
              <Alert severity={licenseResult ? 'success' : 'error'}>
                {licenseResult
                  ? 'License is compatible for fine-tuning and inference'
                  : 'License compatibility issues detected'}
              </Alert>
            )}
          </TabPanel>
        )}
      </Paper>

      {/* Delete Confirmation Dialog */}
      <Dialog open={deleteDialogOpen} onClose={() => setDeleteDialogOpen(false)}>
        <DialogTitle>Delete Artifact?</DialogTitle>
        <DialogContent>
          Are you sure you want to delete "{artifact.metadata.name}"? This action cannot be undone.
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDeleteDialogOpen(false)}>Cancel</Button>
          <Button onClick={handleDelete} color="error" variant="contained">
            Delete
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}