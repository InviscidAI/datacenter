// components/StepOptimization.jsx

import { useState, useEffect, Suspense } from 'react';
import { Paper, Title, Button, Text, Center, Loader, Alert, Grid, NumberInput, Group, Code, SegmentedControl, Card, Box } from '@mantine/core';
import { IconPlayerPlay, IconRefresh } from '@tabler/icons-react';
import { Canvas } from '@react-three/fiber';
import { useGLTF, Environment, OrbitControls, Html } from '@react-three/drei';
import { simClient } from '../api';

function getBoundingBox(points) {
    let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
    if (!points || points.length === 0) return null;
    points.forEach(([x, y]) => {
        minX = Math.min(minX, x);
        minY = Math.min(minY, y);
        maxX = Math.max(maxX, x);
        maxY = Math.max(maxY, y);
    });
    return { x_min: minX, y_min: minY, x_max: maxX, y_max: maxY };
}

// --- FIX: Unified the hook to prevent state loss on tab switching.
function useSimulationStatus(runId) {
    const [status, setStatus] = useState(runId ? 'running' : null);
    useEffect(() => {
        if (!runId) {
            setStatus(null);
            return;
        }
        // Set status to ensure we show a loader if the component mounts with a new runId
        setStatus('running');
        const interval = setInterval(async () => {
            try {
                const response = await simClient.get(`/simulation-status/${runId}`);
                const currentStatus = response.data.status;
                setStatus(currentStatus); // Update status directly
                if (currentStatus !== 'running' && currentStatus !== 'running_optimization') {
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

// --- FIX: ModelViewer now correctly orients the model to match the setup view.
function ModelViewer({ url, room }) {
    const { scene } = useGLTF(url);
    const position = room ? [-room.width / 2, 0, room.length / 2] : [0, 0, 0];
    const scale = [1, 1, -1];
    return <primitive object={scene} scale={scale} position={position} />;
}

function CanvasLoader() {
  return (<Html center><Text color="white">Loading 3D Model...</Text></Html>);
}

function OptimizationResultDisplay({ runId, type }) {
    const [resultData, setResultData] = useState(null);
    const [error, setError] = useState('');

    useEffect(() => {
        if (runId) {
            simClient.get(`/get-result/${runId}/optimization_result.json`)
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
    
    const { room } = appState;
    const initialSimStatus = useSimulationStatus(appState.runId);
    const optimStatus = useSimulationStatus(optimRunId);
    
    const isRunning = optimStatus === 'running' || optimStatus === 'running_optimization' || initialSimStatus === 'running';

    const generateGAConfig = (objects, roomConfig) => {
        if (!roomConfig || !roomConfig.contour || !roomConfig.contour.points) {
            setError("Cannot run GA optimization. A room outline was not detected in the uploaded image.");
            return null;
        }
        const config = {
            room: roomConfig.contour,
            objects: objects.map(obj => ({
                name: obj.id,
                category: obj.category,
                bounding_box: obj.bounding_box || getBoundingBox(obj.contour.points),
                properties: obj.properties 
            })),
            physics: {
                crac_supply_temp_K: 291.15
            }
        };
        if (config.objects.some(o => !o.bounding_box)) {
             setError("Cannot run GA optimization. Some objects are missing geometry data.");
             return null;
        }
        return config;
    };

    const originalModelUrl = (initialSimStatus === 'completed' && appState.runId) ? `${simClient.defaults.baseURL}/get-result/${appState.runId}/${view}.gltf` : null;
    const optimizedModelUrl = (optimStatus === 'completed' && optimRunId) ? `${simClient.defaults.baseURL}/get-result/${optimRunId}/${view}.gltf` : null;

    const handleRun = async (type) => {
        setError('');
        setOptimRunId(null);
        setOptimType(type);

        let config;
        let endpoint;

        if (type === 'binary-search') {
            config = initialGenerateConfig(appState.objects, appState.room);
            if (!config.room.dims) {
                setError("Cannot run temperature optimization. Room dimensions are missing.");
                return;
            }
            config.optimization_params = { target_max_temp_K: targetTemp + 273.15 };
            endpoint = '/run-binary-search';

        } else if (type === 'ga') {
            config = generateGAConfig(appState.objects, appState.room);
            if (!config) return;
            endpoint = '/run-ga-optimization';

        } else {
            return;
        }

        try {
            const response = await simClient.post(endpoint, config);
            setOptimRunId(response.data.run_id);
        } catch (err) {
            const errorMessage = err.response?.data?.error || err.message;
            setError(`Failed to start ${type} optimization: ${errorMessage}`);
            setOptimType(null);
        }
    };

    const resetOptimization = () => {
        setOptimRunId(null);
        setOptimType(null);
        setError('');
    };

    const renderBeforeOptimizationContent = () => {
        if (initialSimStatus === 'running') {
            return <Center style={{height: '100%'}}><Loader /><Text ml="md" c="dimmed">Running initial sim...</Text></Center>;
        }
        if (initialSimStatus === 'completed' && originalModelUrl) {
            return (
                <Canvas key={originalModelUrl}>
                    <Suspense fallback={<CanvasLoader />}>
                        <ModelViewer url={originalModelUrl} room={room} />
                        <Environment preset="city" />
                        <OrbitControls />
                    </Suspense>
                </Canvas>
            );
        }
        if (initialSimStatus === 'failed') {
            return <Center style={{height: '100%'}}><Alert color="red" title="Initial Simulation Failed" /></Center>;
        }
        return <Center style={{height: '100%'}}><Text c="dimmed">Run a base simulation first.</Text></Center>;
    };

    return (
        <Paper shadow="md" p="xl" withBorder>
            {error && <Alert color="red" title="Error" my="md" onClose={() => setError('')} withCloseButton>{error}</Alert>}

            <Grid gutter="xl">
                <Grid.Col span={{ base: 12, lg: 4 }}>
                    <Title order={4}>Optimization Controls</Title>
                    <Text c="dimmed" size="sm" mb="xl">Choose an optimization workflow.</Text>

                    <Card withBorder p="lg" radius="md">
                        <Title order={5}>1. Temperature Optimization</Title>
                        <Text size="sm" c="dimmed" mt="xs" mb="md">Find the highest CRAC temperature that keeps equipment safe.</Text>
                        <Group align="flex-end">
                            <NumberInput label="Max Allowed Temp (°C)" value={targetTemp} onChange={setTargetTemp} min={25} max={50} disabled={isRunning} />
                            <Button onClick={() => handleRun('binary-search')} disabled={!appState.runId || isRunning} loading={optimType === 'binary-search' && isRunning} leftSection={<IconPlayerPlay size={16} />}>Run</Button>
                        </Group>
                    </Card>

                    <Card withBorder p="lg" radius="md" mt="xl">
                        <Title order={5}>2. Layout Optimization (GA)</Title>
                        <Text size="sm" c="dimmed" mt="xs" mb="md">Find the best rack layout to minimize hot spots.</Text>
                        <Button onClick={() => handleRun('ga')} disabled={!appState.runId || isRunning} loading={optimType === 'ga' && isRunning} leftSection={<IconPlayerPlay size={16} />}>Run</Button>
                    </Card>

                    {optimStatus && !isRunning && (
                         <Button mt="xl" variant="light" onClick={resetOptimization} leftSection={<IconRefresh size={16}/>}>
                            Run New Optimization
                         </Button>
                    )}
                </Grid.Col>

                <Grid.Col span={{ base: 12, lg: 8 }}>
                    <Center>
                        <SegmentedControl value={view} onChange={setView} data={['temperature', 'velocity']} mb="md" />
                    </Center>
                    <Grid>
                        <Grid.Col span={6}>
                            <Title order={5} ta="center">Before Optimization</Title>
                            <Paper shadow="md" withBorder style={{ height: '40vh', display: 'flex', justifyContent: 'center', alignItems: 'center' }}>
                               {renderBeforeOptimizationContent()}
                            </Paper>
                        </Grid.Col>
                        <Grid.Col span={6}>
                            <Title order={5} ta="center">After Optimization</Title>
                            <Paper shadow="md" withBorder style={{ height: '40vh', display: 'flex', justifyContent: 'center', alignItems: 'center' }}>
                                {(optimStatus === 'running' || optimStatus === 'running_optimization') && <><Loader /><Text ml="md" c="dimmed">Running...</Text></>}
                                {optimStatus === 'failed' && <Alert color="red" title="Optimization Failed" />}
                                {!(optimStatus === 'running' || optimStatus === 'running_optimization') && !optimizedModelUrl && <Text c="dimmed">Results will appear here.</Text>}
                                {optimStatus === 'completed' && optimizedModelUrl && (
                                    <Canvas key={optimizedModelUrl}>
                                        <Suspense fallback={<CanvasLoader />}>
                                            <ModelViewer url={optimizedModelUrl} room={room} />
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