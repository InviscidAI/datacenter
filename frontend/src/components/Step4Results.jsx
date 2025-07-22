// components/Step4Results.jsx

import { useState, useEffect, Suspense, useMemo } from 'react';
import { Paper, Title, Button, Text, Center, Loader, SegmentedControl, Alert, Grid, ScrollArea, Textarea, SimpleGrid } from '@mantine/core';
import { IconAlertCircle, IconPlayerPlay, IconSend } from '@tabler/icons-react';
import { Canvas } from '@react-three/fiber';
import { OrbitControls, useGLTF, Environment, Html } from '@react-three/drei';
import apiClient from '../api';
import { v4 as uuidv4 } from 'uuid';
import { ThreeDScene, PropertyEditor } from './Step3Visualize';

function useSimulationStatus(runId) {
    const [status, setStatus] = useState(null);
    useEffect(() => {
        if (runId) { setStatus('running'); } else { setStatus(null); return; }
        const interval = setInterval(async () => {
            try {
                const response = await apiClient.get(`/simulation-status/${runId}`);
                if (response.data.status !== 'running' && response.data.status !== 'running_optimization') {
                    setStatus(response.data.status);
                    clearInterval(interval);
                }
            } catch { setStatus('failed'); clearInterval(interval); }
        }, 3000);
        return () => clearInterval(interval);
    }, [runId]);
    return status;
}

function ModelViewer({ url }) {
    const { scene } = useGLTF(url);
    return <primitive key={url} object={scene} scale={1} />;
}

function CanvasLoader() {
  return (<Html center><div style={{ color: 'white' }}>Loading 3D Model...</div></Html>);
}

// FIX: Chatbot now takes the current config and an update handler
function Chatbot({ currentConfig, onChatbotUpdate }) {
    const [sessionId] = useState(() => `session_${uuidv4()}`);
    const [message, setMessage] = useState('');
    const [history, setHistory] = useState([]);
    const [loading, setLoading] = useState(false);

    const handleSend = async () => {
        if (!message) return;
        const newHistory = [...history, { role: 'user', content: message }];
        setHistory(newHistory);
        setMessage('');
        setLoading(true);

        try {
            // Pass the current state of the what-if config to the chatbot backend
            const response = await apiClient.post('/chat/send', { 
                session_id: sessionId, 
                message, 
                config: currentConfig 
            });
            
            const reply = response.data.reply;
            setHistory(prev => [...prev, { role: 'assistant', content: JSON.stringify(reply, null, 2) }]);
            
            // Pass the raw reply up to the parent to handle the state update
            if (reply.action) {
                onChatbotUpdate(reply);
            }
        } catch (err) {
            setHistory(prev => [...prev, { role: 'assistant', content: 'Error processing request.' }]);
        } finally {
            setLoading(false);
        }
    };

    return (
        <Paper withBorder p="sm" style={{ height: '100%' }}>
            <Title order={5}>Chatbot Assistant</Title>
            <ScrollArea style={{ height: 300 }} my="sm">
                {history.map((item, index) => <Paper key={index} withBorder p="xs" mb="xs" bg={item.role === 'user' ? 'gray.1' : 'blue.0'}><Text size="sm" style={{ whiteSpace: 'pre-wrap' }}>{item.content}</Text></Paper>)}
            </ScrollArea>
            <Textarea placeholder="e.g., 'What if CRAC 2 fails?'" value={message} onChange={(e) => setMessage(e.currentTarget.value)} disabled={loading} />
            <Button fullWidth mt="xs" onClick={handleSend} disabled={loading} rightSection={<IconSend size={16}/>}>Send</Button>
        </Paper>
    );
}


export default function Step4Results({ appState, setAppState, onReset, generateConfig, categories, pxToMeters }) {
    const { runId, whatIfRunId, objects: originalObjects, room, room: { contour: roomContour } } = appState;
    const originalStatus = useSimulationStatus(runId);
    const whatIfStatus = useSimulationStatus(whatIfRunId);
    
    const [view, setView] = useState('temperature');
    const [whatIfObjects, setWhatIfObjects] = useState(null);
    const [selectedWhatIfObjectId, setSelectedWhatIfObjectId] = useState(null);

    useEffect(() => {
        if (originalObjects) {
            setWhatIfObjects(JSON.parse(JSON.stringify(originalObjects))); // Deep copy
        }
    }, [originalObjects]);

    const modelUrl = (originalStatus === 'completed' && runId) ? `${apiClient.defaults.baseURL}/get-result/${runId}/${view}.gltf` : null;
    const whatIfModelUrl = (whatIfStatus === 'completed' && whatIfRunId) ? `${apiClient.defaults.baseURL}/get-result/${whatIfRunId}/${view}.gltf` : null;

    const selectedWhatIfObject = useMemo(() => {
        return whatIfObjects?.find(o => o.id === selectedWhatIfObjectId);
    }, [selectedWhatIfObjectId, whatIfObjects]);

    const handleWhatIfPropertyChange = (propName, value) => {
        setWhatIfObjects(prevObjects =>
            prevObjects.map(obj =>
                obj.id === selectedWhatIfObjectId
                    ? { ...obj, properties: { ...obj.properties, [propName]: value ?? 0 } }
                    : obj
            )
        );
    };

    // FIX: A new handler to process updates coming from the chatbot
    const handleChatbotUpdate = (reply) => {
        setWhatIfObjects(prevObjects => {
            const getSimType = (category) => {
                if (category === 'Data Rack') return 'rack';
                if (category === 'CRAC') return 'crac';
                if (category === 'Perforated Tile') return 'tile';
                return 'obj'; // Fallback
            };

            if (reply.action === 'delete') {
                return prevObjects.filter(obj => {
                    const simType = getSimType(obj.category);
                    const numId = obj.id.split('_')[1];
                    const objSimName = `${simType}_${numId}`;
                    // The comparison is now correct
                    return objSimName !== reply.target_name;
                });
            }

            if (reply.action === 'update') {
                return prevObjects.map(obj => {
                    const simType = getSimType(obj.category);
                    const numId = obj.id.split('_')[1];
                    const objSimName = `${simType}_${numId}`;

                    // The comparison is now correct
                    if (objSimName === reply.target_name || reply.target_name === 'all') {
                        const newProperties = { ...obj.properties, ...reply.parameters };
                        return { ...obj, properties: newProperties };
                    }
                    return obj;
                });
            }
            return prevObjects;
        });
    };
    
    const handleRunWhatIf = async () => {
        if (!whatIfObjects) return;
        try {
            const configToRun = generateConfig(whatIfObjects, room);
            const response = await apiClient.post('/run-simulation', configToRun);
            setAppState(prev => ({ ...prev, whatIfRunId: response.data.run_id }));
        } catch (error) {
            console.error("Failed to run what-if simulation:", error);
        }
    };

    // FIX: Dedicated rendering logic for the Original Result panel
    let originalResultContent;
    if (originalStatus === 'running') {
        originalResultContent = <Center style={{height: '100%'}}><Loader /></Center>;
    } else if (originalStatus === 'completed' && modelUrl) {
        originalResultContent = (<Canvas key={modelUrl}><Suspense fallback={<CanvasLoader />}><ModelViewer url={modelUrl} /><Environment preset="city" /><OrbitControls /></Suspense></Canvas>);
    } else if (originalStatus === 'failed') {
        originalResultContent = <Alert color="red" title="Initial Simulation Failed" />;
    } else {
        originalResultContent = <Center style={{height: '100%'}}><Text c="dimmed">Original result not available.</Text></Center>;
    }

    let whatIfResultContent;
    if (whatIfStatus === 'running') {
        whatIfResultContent = <Center style={{height: '100%'}}><Loader/></Center>;
    } else if (whatIfStatus === 'completed' && whatIfModelUrl) {
        whatIfResultContent = (<Canvas key={whatIfModelUrl}><Suspense fallback={<CanvasLoader />}><ModelViewer url={whatIfModelUrl} /><Environment preset="city" /><OrbitControls /></Suspense></Canvas>);
    } else if (whatIfStatus === 'failed') {
        whatIfResultContent = <Alert color="red" title="What-If Simulation Failed" />;
    } else {
        whatIfResultContent = <Center style={{height: '100%'}}><Text c="dimmed">Run a "what-if" scenario to see results here.</Text></Center>;
    }

    if (!whatIfObjects) {
        return <Center style={{height: '50vh'}}><Loader /></Center>;
    }

    return (
        <>
            <Center><SegmentedControl value={view} onChange={setView} data={['temperature', 'velocity']} mb="md" /></Center>
            <Grid>
                <Grid.Col span={{ base: 12, md: 6 }}>
                    <Title order={4} align="center">Original Result</Title>
                    <Paper shadow="md" withBorder style={{ height: '50vh' }}>
                        {originalResultContent}
                    </Paper>
                </Grid.Col>
                <Grid.Col span={{ base: 12, md: 6 }}>
                     <Title order={4} align="center">"What If?" Result</Title>
                     <Paper shadow="md" withBorder style={{ height: '50vh' }}>{whatIfResultContent}</Paper>
                </Grid.Col>
                <Grid.Col span={12} mt="xl">
                    <Paper withBorder p="md">
                        <Title order={3}>"What If?" Scenario Builder</Title>
                        <Text c="dimmed" size="sm" mb="lg">Manually click objects to edit properties, or use the chatbot for automated changes.</Text>
                        <Grid>
                            <Grid.Col span={{ base: 12, lg: 7 }}>
                                <Paper withBorder style={{height: '100%', minHeight: 450}}>
                                     <ThreeDScene 
                                        objects={whatIfObjects}
                                        room={room}
                                        categories={categories}
                                        pxToMeters={pxToMeters}
                                        onObjectClick={setSelectedWhatIfObjectId}
                                        selectedObjectId={selectedWhatIfObjectId}
                                        roomContour={roomContour}
                                     />
                                </Paper>
                            </Grid.Col>
                             <Grid.Col span={{ base: 12, lg: 5 }}>
                                <SimpleGrid cols={1} spacing="md">
                                    <Paper withBorder p="sm">
                                        <Title order={5}>Manual Editor</Title>
                                        <PropertyEditor 
                                            object={selectedWhatIfObject} 
                                            onPropertyChange={handleWhatIfPropertyChange} 
                                        />
                                    </Paper>
                                    <Chatbot
                                        currentConfig={generateConfig(whatIfObjects, room)}
                                        onChatbotUpdate={handleChatbotUpdate}
                                    />
                                </SimpleGrid>
                             </Grid.Col>
                        </Grid>
                        <Center mt="lg">
                            <Button size="lg" color="green" onClick={handleRunWhatIf} leftSection={<IconPlayerPlay />} loading={whatIfStatus === 'running'}>
                                Run "What If" Simulation
                            </Button>
                        </Center>
                    </Paper>
                </Grid.Col>
            </Grid>
            <Center mt="xl"><Button onClick={onReset} variant="light">Start New Design</Button></Center>
        </>
    );
}