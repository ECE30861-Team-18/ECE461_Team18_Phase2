import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Box,
  Paper,
  Typography,
  TextField,
  Button,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Chip,
  IconButton,
  InputAdornment,
  Alert,
  CircularProgress,
  ToggleButtonGroup,
  ToggleButton,
  Stack,
} from '@mui/material';
import SearchIcon from '@mui/icons-material/Search';
import FilterIcon from '@mui/icons-material/FilterList';
import ViewIcon from '@mui/icons-material/Visibility';
import RefreshIcon from '@mui/icons-material/Refresh';
import { ArtifactMetadata, ArtifactType } from '../types';
import apiClient from '../api';

const artifactTypeColors: Record<ArtifactType, 'primary' | 'success' | 'warning'> = {
  model: 'primary',
  dataset: 'success',
  code: 'warning',
};

export default function ArtifactsPage() {
  const [artifacts, setArtifacts] = useState<ArtifactMetadata[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [searchTerm, setSearchTerm] = useState('');
  const [filterTypes, setFilterTypes] = useState<ArtifactType[]>([]);
  const [searchMode, setSearchMode] = useState<'name' | 'regex'>('name');
  
  const navigate = useNavigate();

  const loadArtifacts = async () => {
    setLoading(true);
    setError('');

    try {
      let result: ArtifactMetadata[];

      if (searchMode === 'regex' && searchTerm) {
        // RegEx search
        result = await apiClient.searchArtifactsByRegex({ regex: searchTerm });
      } else if (searchTerm && searchTerm !== '*') {
        // Name search
        result = await apiClient.getArtifactsByName(searchTerm);
      } else {
        // List all artifacts
        const response = await apiClient.listArtifacts([{ name: '*' }]);
        result = response.data;
      }

      // Apply type filters
      if (filterTypes.length > 0) {
        result = result.filter((artifact) =>
          filterTypes.includes(artifact.type)
        );
      }

      setArtifacts(result);
    } catch (err: any) {
      setError(err.message || 'Failed to load artifacts');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadArtifacts();
  }, []);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    loadArtifacts();
  };

  const handleFilterChange = (
    _: React.MouseEvent<HTMLElement>,
    newFilters: ArtifactType[]
  ) => {
    setFilterTypes(newFilters);
  };

  const handleViewArtifact = (artifact: ArtifactMetadata) => {
    navigate(`/artifacts/${artifact.type}/${artifact.id}`);
  };

  return (
    <Box>
      <Typography variant="h4" gutterBottom>
        Artifacts
      </Typography>

      <Paper sx={{ p: 3, mb: 3 }}>
        <form onSubmit={handleSearch}>
          <Stack spacing={2}>
            <Box sx={{ display: 'flex', gap: 2, alignItems: 'flex-start' }}>
              <TextField
                fullWidth
                label={searchMode === 'regex' ? 'RegEx Pattern' : 'Search by name'}
                placeholder={
                  searchMode === 'regex'
                    ? '.*?(audience|bert).*'
                    : 'Enter artifact name or * for all'
                }
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                InputProps={{
                  startAdornment: (
                    <InputAdornment position="start">
                      <SearchIcon />
                    </InputAdornment>
                  ),
                }}
              />
              <ToggleButtonGroup
                value={searchMode}
                exclusive
                onChange={(_, value) => value && setSearchMode(value)}
                aria-label="search mode"
              >
                <ToggleButton value="name" aria-label="name search">
                  Name
                </ToggleButton>
                <ToggleButton value="regex" aria-label="regex search">
                  RegEx
                </ToggleButton>
              </ToggleButtonGroup>
              <Button
                type="submit"
                variant="contained"
                disabled={loading}
                sx={{ minWidth: 120 }}
              >
                Search
              </Button>
              <IconButton onClick={loadArtifacts} disabled={loading}>
                <RefreshIcon />
              </IconButton>
            </Box>

            <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
              <FilterIcon />
              <Typography variant="body2">Filter by type:</Typography>
              <ToggleButtonGroup
                value={filterTypes}
                onChange={handleFilterChange}
                aria-label="artifact type filter"
              >
                <ToggleButton value="model" aria-label="model">
                  Models
                </ToggleButton>
                <ToggleButton value="dataset" aria-label="dataset">
                  Datasets
                </ToggleButton>
                <ToggleButton value="code" aria-label="code">
                  Code
                </ToggleButton>
              </ToggleButtonGroup>
            </Box>
          </Stack>
        </form>
      </Paper>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}

      {loading ? (
        <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}>
          <CircularProgress />
        </Box>
      ) : (
        <TableContainer component={Paper}>
          <Table>
            <TableHead>
              <TableRow>
                <TableCell>Name</TableCell>
                <TableCell>ID</TableCell>
                <TableCell>Type</TableCell>
                <TableCell align="right">Actions</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {artifacts.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={4} align="center">
                    <Typography variant="body2" color="text.secondary" py={4}>
                      No artifacts found. Try adjusting your search or filters.
                    </Typography>
                  </TableCell>
                </TableRow>
              ) : (
                artifacts.map((artifact) => (
                  <TableRow
                    key={artifact.id}
                    hover
                    sx={{ cursor: 'pointer' }}
                    onClick={() => handleViewArtifact(artifact)}
                  >
                    <TableCell>
                      <Typography variant="body1" fontWeight="medium">
                        {artifact.name}
                      </Typography>
                    </TableCell>
                    <TableCell>
                      <Typography variant="body2" color="text.secondary">
                        {artifact.id}
                      </Typography>
                    </TableCell>
                    <TableCell>
                      <Chip
                        label={artifact.type}
                        color={artifactTypeColors[artifact.type]}
                        size="small"
                      />
                    </TableCell>
                    <TableCell align="right">
                      <IconButton
                        size="small"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleViewArtifact(artifact);
                        }}
                      >
                        <ViewIcon />
                      </IconButton>
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </TableContainer>
      )}

      <Box sx={{ mt: 2, display: 'flex', justifyContent: 'space-between' }}>
        <Typography variant="body2" color="text.secondary">
          Showing {artifacts.length} artifact{artifacts.length !== 1 ? 's' : ''}
        </Typography>
        <Button
          variant="outlined"
          onClick={() => navigate('/artifacts/create')}
        >
          Create New Artifact
        </Button>
      </Box>
    </Box>
  );
}