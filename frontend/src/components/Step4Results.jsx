import { useState, useEffect, Suspense } from 'react';
import { Paper, Title, Button, Text, Center, Loader, SegmentedControl, Alert, SimpleGrid, Divider } from '@mantine/core';
import { IconAlertCircle } from '@tabler/icons-react';
import { Canvas } from '@react-three/fiber';
import { OrbitControls, useGLTF, Environment, Html } from '@react-three/drei';
import axios from 'axios';
import apiClient, { API_BASE_URL } from '../api';

// A custom hook for polling
function useSimulationStatus(runId) {
    const [status, setStatus] = useState(runId ? 'running' : 'pending');

    useEffect(() => {
        if (!runId || status === 'completed' || status === 'failed') {
            return;
        }

        const interval = setInterval(async () => {
            try {
                const response = await apiClient.get(`/simulation-status/${runId}`);
                if (response.data.status !== 'running') {
                    setStatus(response.data.status);
                    clearInterval(interval);
                }
            } catch {
                setStatus('failed');
                clearInterval(interval);
            }
        }, 3000);

        return () => clearInterval(interval);
    }, [runId, status]);

    return status;
}

function ModelViewer({ url }) {
    const { scene } = useGLTF(url);
    // Add a scaling factor if the model appears too small or large
    return <primitive object={scene} scale={1} />;
}

function CanvasLoader() {
  return (
    <Html center>
      <Loader />
    </Html>
  );
}

function KpiStat({ title, value, unit, description }) {
    return (
        <Paper withBorder p="md" radius="md">
            <Text size="xs" c="dimmed" tt="uppercase">{title}</Text>
            <Text fz="xl" fw={700}>
                {value}
                {unit && <Text span c="dimmed" fw={500} size="sm"> {unit}</Text>}
            </Text>
            {description && <Text fz="xs" c="dimmed" mt={4}>{description}</Text>}
        </Paper>
    );
}

export default function Step4Results({ appState, onReset }) {
    const { runId, kpiResults } = appState;
    const status = useSimulationStatus(runId);
    const [view, setView] = useState('temperature');
    const modelUrl = `${API_BASE_URL}/api/get-result/${runId}/${view}.gltf`;

    if (!runId) {
        return (
            <Center style={{ height: '50vh', flexDirection: 'column' }}>
                <Title order={3} color="red">Error</Title>
                <Text c="dimmed">No simulation run ID found. Please go back and start a new simulation.</Text>
            </Center>
        );
    }

    if (status === 'running') {
        return (
            <Center style={{ height: '50vh', flexDirection: 'column' }}>
                <Loader size="xl" />
                <Title order={3} mt="xl">Simulation in progress...</Title>
                <Text c="dimmed">This may take several minutes. Please wait.</Text>
            </Center>
        );
    }
    
    if (status === 'failed') {
        return (
            <Center style={{ height: '50vh' }}>
                <Alert icon={<IconAlertCircle size="1rem" />} title="Simulation Failed!" color="red" radius="md">
                    Check the backend console and `log.txt` in `backend/simulations/{runId}` for details.
                </Alert>
            </Center>
        );
    }

    if (status === 'completed') {
        return (
            <>
                <Center>
                    <SegmentedControl value={view} onChange={setView} data={['temperature   ', 'velocity']} mb="md" />
                </Center>
                <Paper shadow="md" withBorder style={{ height: '60vh' }}>
                    <Canvas camera={{ position: [appState.room.width / 2, 5, appState.room.length * 1.5], fov: 50 }}>
                        {/* --- USE THE 3D-COMPATIBLE LOADER IN THE FALLBACK --- */}
                        <Suspense fallback={<CanvasLoader />}>
                            <ModelViewer url={modelUrl} />
                        </Suspense>
                        <Environment preset="city" />
                        <OrbitControls />
                    </Canvas>
                </Paper>
                {kpiResults && (
                    <>
                        <Divider my="xl" label="Efficiency Dashboard" labelPosition="center" />
                        <SimpleGrid cols={{ base: 1, sm: 2, md: 4 }}>
                            <KpiStat
                                title="Total Energy Consumption (EDC)"
                                value={kpiResults.edc_kwh_year.toLocaleString('en-US', { maximumFractionDigits: 0 })}
                                unit="kWh/yr"
                                description="Total energy for IT and cooling systems."
                            />
                            <KpiStat
                                title="Power Usage Effectiveness (PUE)"
                                value={kpiResults.pue.toFixed(2)}
                                unit=""
                                description="Total Facility Power / IT Power"
                            />
                             <KpiStat
                                title="Cooling Efficiency Ratio (CER)"
                                value={kpiResults.cer.toFixed(2)}
                                unit=""
                                description="Heat Removed / Cooling Energy"
                            />
                            <KpiStat
                                title="Annual IT Power Cost"
                                value={`$${kpiResults.spc_per_year.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`}
                                unit="/yr"
                                description="Includes PUE in total cost calculation."
                            />
                        </SimpleGrid>
                    </>
                )}
                {/* --- END: KPI Dashboard Section --- */}
                <Center mt="xl">
                    <Button onClick={onReset} variant="light">Start New Simulation</Button>
                </Center>
            </>
        );
    }

    return null; // Should not be reached
}