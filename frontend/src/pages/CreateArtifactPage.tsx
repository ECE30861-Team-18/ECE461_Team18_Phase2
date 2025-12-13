import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Box,
  Paper,
  Typography,
  TextField,
  Button,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Alert,
  CircularProgress,
  Link,
} from '@mui/material';
import {
  ArrowBack as BackIcon,
  CloudUpload as UploadIcon,
} from '@mui/icons-material';
import { ArtifactType } from '../types';
import apiClient from '../api';

export default function CreateArtifactPage() {
  const navigate = useNavigate();

  const [artifactType, setArtifactType] = useState<ArtifactType>('model');
  const [sourceUrl, setSourceUrl] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setSuccess(false);
    setLoading(true);

    try {
      const result = await apiClient.createArtifact(artifactType, {
        url: sourceUrl,
      });

      setSuccess(true);
      
      // Redirect to the new artifact after a brief delay
      setTimeout(() => {
        navigate(`/artifacts/${result.metadata.type}/${result.metadata.id}`);
      }, 1500);
    } catch (err: any) {
      setError(err.message || 'Failed to create artifact');
    } finally {
      setLoading(false);
    }
  };

  const exampleUrls: Record<ArtifactType, string> = {
    model: 'https://huggingface.co/google-bert/bert-base-uncased',
    dataset: 'https://huggingface.co/datasets/bookcorpus',
    code: 'https://github.com/openai/whisper',
  };

  return (
    <Box>
      <Button
        startIcon={<BackIcon />}
        onClick={() => navigate('/artifacts')}
        sx={{ mb: 3 }}
      >
        Back to Artifacts
      </Button>

      <Typography variant="h4" gutterBottom>
        Create New Artifact
      </Typography>

      <Paper sx={{ p: 4, maxWidth: 800 }}>
        <form onSubmit={handleSubmit}>
          <FormControl fullWidth sx={{ mb: 3 }}>
            <InputLabel id="artifact-type-label">Artifact Type</InputLabel>
            <Select
              labelId="artifact-type-label"
              id="artifact-type"
              value={artifactType}
              label="Artifact Type"
              onChange={(e) => setArtifactType(e.target.value as ArtifactType)}
            >
              <MenuItem value="model">Model</MenuItem>
              <MenuItem value="dataset">Dataset</MenuItem>
              <MenuItem value="code">Code</MenuItem>
            </Select>
          </FormControl>

          <TextField
            fullWidth
            required
            label="Source URL"
            placeholder={exampleUrls[artifactType]}
            value={sourceUrl}
            onChange={(e) => setSourceUrl(e.target.value)}
            helperText="Provide a downloadable URL pointing to the artifact bundle"
            sx={{ mb: 3 }}
          />

          <Box
            sx={{
              mb: 3,
              p: 2,
              bgcolor: 'grey.100',
              borderRadius: 1,
              border: '1px solid',
              borderColor: 'grey.300',
            }}
          >
            <Typography variant="subtitle2" gutterBottom>
              Example URLs for {artifactType}:
            </Typography>
            <Typography variant="body2" component="div">
              <Link
                href={exampleUrls[artifactType]}
                target="_blank"
                rel="noopener noreferrer"
              >
                {exampleUrls[artifactType]}
              </Link>
            </Typography>
            <Typography variant="caption" color="text.secondary" sx={{ mt: 1, display: 'block' }}>
              Supported sources: Hugging Face, GitHub, direct download links
            </Typography>
          </Box>

          {error && (
            <Alert severity="error" sx={{ mb: 3 }}>
              {error}
            </Alert>
          )}

          {success && (
            <Alert severity="success" sx={{ mb: 3 }}>
              Artifact created successfully! Redirecting...
            </Alert>
          )}

          <Box sx={{ display: 'flex', gap: 2 }}>
            <Button
              type="submit"
              variant="contained"
              size="large"
              startIcon={loading ? <CircularProgress size={20} /> : <UploadIcon />}
              disabled={loading || !sourceUrl}
              fullWidth
            >
              {loading ? 'Creating Artifact...' : 'Create Artifact'}
            </Button>
            <Button
              variant="outlined"
              onClick={() => navigate('/artifacts')}
              disabled={loading}
            >
              Cancel
            </Button>
          </Box>
        </form>

        <Box sx={{ mt: 4, p: 2, bgcolor: 'info.light', borderRadius: 1 }}>
          <Typography variant="subtitle2" gutterBottom>
            📝 Note:
          </Typography>
          <Typography variant="body2">
            • Artifacts will be automatically assigned a unique ID
            <br />
            • Models will be evaluated and rated automatically
            <br />
            • Rating may be performed asynchronously (HTTP 202 response)
            <br />• Artifacts with disqualified ratings will not be registered (HTTP 424)
          </Typography>
        </Box>
      </Paper>
    </Box>
  );
}