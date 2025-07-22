// components/StepOptimization.jsx

import { useState, useEffect, Suspense } from 'react';
import { Paper, Title, Button, Text, Center, Loader, Alert, Grid, NumberInput, Group, Code, SegmentedControl, Card, Box } from '@mantine/core';
import { IconPlayerPlay, IconRefresh, IconArrowRight } from '@tabler/icons-react';
import { Canvas } from '@react-three/fiber';
import { useGLTF, Environment, OrbitControls, Html } from '@react-three/drei';
import apiClient from '../api';

// Helper hook from Step4Results - no changes needed
function useSimulationStatus(runId) {
    const [status, setStatus] = useState(null);
    useEffect(() => {
        if (!runId) {
            setStatus(null);
            return;
        }
        setStatus('running_optimization'); 
        const interval = setInterval(async () => {
            try {
                const response = await apiClient.get(`/simulation-status/${runId}`);
                const currentStatus = response.data.status;
                if (currentStatus !== 'running' && currentStatus !== 'running_optimization') {
                    setStatus(currentStatus);
                    clearInterval(interval);
                }
            } catch {
                setStatus('failed');
                clearInterval(interval);
            }
        }, 3000);
        return () => clearInterval(interval);
    }, [runId]);
    return status;
}

// Helper components from Step4Results - no changes needed
function ModelViewer({ url }) {
    const { scene } = useGLTF(url);
    return <primitive object={scene} scale={1} />;
}
function CanvasLoader() {
  return (<Html center><Text color="white">Loading 3D Model...</Text></Html>);
}

// --- UPDATED: Component for showing user-friendly results ---
function OptimizationResultDisplay({ runId, type }) {
    const [resultData, setResultData] = useState(null);
    const [error, setError] = useState('');

    useEffect(() => {
        if (runId) {
            apiClient.get(`/get-result/${runId}/optimization_result.json`)
                .then(response => setResultData(response.data))
                .catch(() => setError('Could not load optimization results file.'));
        }
    }, [runId]);

    if (error) {
        return <Alert color="red" title="Error">{error}</Alert>
    }
    if (!resultData) {
        return <Center><Loader size="sm" /></Center>;
    }

    if (type === 'binary-search') {
        const optimalTempC = (resultData.optimal_crac_temp_K - 273.15).toFixed(1);
        const targetTempC = (resultData.target_max_temp_K - 273.15).toFixed(1);
        return (
            <Card withBorder p="md">
                <Text fw={700} size="lg">Temperature Optimization Complete</Text>
                <Text mt="sm">The highest possible CRAC supply temperature is <Text span c="blue" fw={700}>{optimalTempC}°C</Text>.</Text>
                <Text size="sm" c="dimmed">This keeps all equipment below the target of {targetTempC}°C.</Text>
            </Card>
        );
    }

    if (type === 'ga') {
        const initialTempC = resultData.initial_max_temp_K ? (resultData.initial_max_temp_K - 273.15).toFixed(1) : null;
        const bestTempC = (resultData.minimized_max_temp_K - 273.15).toFixed(1);
         return (
            <Card withBorder p="md">
                <Title order={5}>Layout Optimization Complete</Title>
                {initialTempC ? (
                     <Text mt="sm">
                        The best layout reduced the maximum temperature from{' '}
                        <Text span c="orange" fw={700}>{initialTempC}°C</Text> to{' '}
                        <Text span c="blue" fw={700}>{bestTempC}°C</Text>.
                     </Text>
                ) : (
                    <Text mt="sm">The best layout found reduces the maximum equipment temperature to <Text span c="blue" fw={700}>{bestTempC}°C</Text>.</Text>
                )}
                <Text size="sm" c="dimmed" mt={4}>The visualization has been updated to show the optimal component arrangement.</Text>
            </Card>
        );
    }

    return <Code block>{JSON.stringify(resultData, null, 2)}</Code>;
}

export default function StepOptimization({ appState, generateConfig: initialGenerateConfig }) {
    const [optimRunId, setOptimRunId] = useState(null);
    const [optimType, setOptimType] = useState(null); 
    const [error, setError] = useState('');
    const [targetTemp, setTargetTemp] = useState(35);
    const [view, setView] = useState('temperature');

    const optimStatus = useSimulationStatus(optimRunId);
    const isRunning = optimStatus === 'running' || optimStatus === 'running_optimization';
    
    // --- FIX: Create a new, reliable generateConfig function inside the component ---
    const generateConfig = (objects, room) => {
        // This function creates the specific structure the backend optimization routes expect.
        // It's different from the structure needed for a basic simulation.
        if (!room || !room.points) {
            setError("Cannot run optimization without a defined room contour.");
            return null;
        }

        const config = {
            // The top-level structure expected by the GA and Binary Search runners
            room: room, 
            objects: objects.map(obj => ({
                name: obj.id, 
                category: obj.category,
                bounding_box: obj.bounding_box, // This must be calculated in a prior step
            })),
            physics: {
                // Default physics, will be used by the simulation
                crac_supply_temp_K: 291.15 // 18°C
            }
        };
        return config;
    };

    const originalModelUrl = `${apiClient.defaults.baseURL}/get-result/${appState.runId}/${view}.gltf`;
    const optimizedModelUrl = (optimStatus === 'completed' && optimRunId) ? `${apiClient.defaults.baseURL}/get-result/${optimRunId}/${view}.gltf` : null;

    const handleRun = async (type) => {
        setError('');
        setOptimRunId(null);
        setOptimType(type);
        
        // --- FIX: Use the new, reliable generateConfig function ---
        const config = generateConfig(appState.objects, appState.room);
        if (!config) return; // Stop if the config is invalid

        let endpoint = '';
        if (type === 'binary-search') {
            config.optimization_params = { target_max_temp_K: targetTemp + 273.15 };
            endpoint = '/run-binary-search';
        } else if (type === 'ga') {
            endpoint = '/run-ga-optimization';
        } else {
            return;
        }

        try {
            const response = await apiClient.post(endpoint, config);
            setOptimRunId(response.data.run_id);
        } catch (err) {
            setError(`Failed to start ${type} optimization: ${err.response?.data?.error || err.message}`);
            setOptimType(null);
        }
    };
    
    const resetOptimization = () => {
        setOptimRunId(null);
        setOptimType(null);
        setError('');
    };

    return (
        <Paper shadow="md" p="xl" withBorder>
            {error && <Alert color="red" title="Error" my="md" onClose={() => setError('')} withCloseButton>{error}</Alert>}
            
            <Grid gutter="xl">
                {/* COLUMN 1: CONTROLS */}
                <Grid.Col span={{ base: 12, lg: 4 }}>
                    <Title order={4}>Optimization Controls</Title>
                    <Text c="dimmed" size="sm" mb="xl">Choose an optimization workflow.</Text>
                
                    <Card withBorder p="lg" radius="md">
                        <Title order={5}>1. Temperature Optimization</Title>
                        <Text size="sm" c="dimmed" mt="xs" mb="md">Find the highest CRAC temperature that keeps equipment safe.</Text>
                        <Group align="flex-end">
                            <NumberInput label="Max Allowed Temp (°C)" value={targetTemp} onChange={setTargetTemp} min={25} max={50} disabled={isRunning} />
                            <Button onClick={() => handleRun('binary-search')} disabled={!appState.runId || isRunning} leftSection={<IconPlayerPlay size={16} />}>Run</Button>
                        </Group>
                    </Card>

                    <Card withBorder p="lg" radius="md" mt="xl">
                        <Title order={5}>2. Layout Optimization (GA)</Title>
                        <Text size="sm" c="dimmed" mt="xs" mb="md">Find the best rack layout to minimize hot spots.</Text>
                        <Button onClick={() => handleRun('ga')} disabled={!appState.runId || isRunning} leftSection={<IconPlayerPlay size={16} />}>Run</Button>
                    </Card>

                    {optimStatus && !isRunning && (
                         <Button mt="xl" variant="light" onClick={resetOptimization} leftSection={<IconRefresh size={16}/>}>
                            Run New Optimization
                         </Button>
                    )}
                </Grid.Col>

                {/* COLUMN 2: VISUALIZATION & RESULTS */}
                <Grid.Col span={{ base: 12, lg: 8 }}>
                    <Center>
                        <SegmentedControl value={view} onChange={setView} data={['temperature', 'velocity']} mb="md" />
                    </Center>
                    <Grid>
                        <Grid.Col span={6}>
                            <Title order={5} ta="center">Before Optimization</Title>
                            <Paper shadow="md" withBorder style={{ height: '40vh', display: 'flex', justifyContent: 'center', alignItems: 'center' }}>
                                {!appState.runId ? <Text c="dimmed">Run a base simulation first.</Text> :
                                    <Canvas key={originalModelUrl}>
                                        <Suspense fallback={<CanvasLoader />}>
                                            <ModelViewer url={originalModelUrl} />
                                            <Environment preset="city" />
                                            <OrbitControls />
                                        </Suspense>
                                    </Canvas>
                                }
                            </Paper>
                        </Grid.Col>
                        <Grid.Col span={6}>
                            <Title order={5} ta="center">After Optimization</Title>
                            <Paper shadow="md" withBorder style={{ height: '40vh', display: 'flex', justifyContent: 'center', alignItems: 'center' }}>
                                {isRunning && <><Loader /><Text ml="md" c="dimmed">Running...</Text></>}
                                {optimStatus === 'failed' && <Alert color="red" title="Optimization Failed" />}
                                {!isRunning && !optimizedModelUrl && <Text c="dimmed">Results will appear here.</Text>}
                                {optimStatus === 'completed' && optimizedModelUrl && (
                                    <Canvas key={optimizedModelUrl}>
                                        <Suspense fallback={<CanvasLoader />}>
                                            <ModelViewer url={optimizedModelUrl} />
                                            <Environment preset="city" />
                                            <OrbitControls />
                                        </Suspense>
                                    </Canvas>
                                )}
                            </Paper>
                        </Grid.Col>
                    </Grid>
                    
                    {optimStatus === 'completed' && optimRunId && (
                        <Box mt="xl">
                           <OptimizationResultDisplay runId={optimRunId} type={optimType} />
                        </Box>
                    )}
                </Grid.Col>
            </Grid>
        </Paper>
    );
}