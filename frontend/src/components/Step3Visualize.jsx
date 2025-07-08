import { useState, useMemo } from 'react';
import { Grid, Paper, Title, Button, Group, Text, NumberInput, Code, ScrollArea, SimpleGrid, Center } from '@mantine/core';
import { Canvas } from '@react-three/fiber';
import { OrbitControls, Box, Text as DreiText } from '@react-three/drei';
import axios from 'axios';
import apiClient from '../api';

// Helper to calculate bounding box from contour points
function getBoundingBox(points) {
    let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
    points.forEach(([x, y]) => {
        minX = Math.min(minX, x);
        minY = Math.min(minY, y);
        maxX = Math.max(maxX, x);
        maxY = Math.max(maxY, y);
    });
    return { x: minX, y: minY, width: maxX - minX, height: maxY - minY };
}

function ThreeDScene({ objects, room, categories, pxToMeters, onObjectClick, selectedObjectId }) {
    const roomCenter = { x: room.width / 2, y: room.length / 2 };

    const objectMeshes = useMemo(() => objects.map(obj => {
        const bbox = getBoundingBox(obj.contour.points);
        const width = bbox.width * pxToMeters;
        const depth = bbox.height * pxToMeters;
        const height = obj.properties.height;
        // Position relative to room center
        const x = (bbox.x + bbox.width / 2) * pxToMeters - roomCenter.x;
        const z = -((bbox.y + bbox.height / 2) * pxToMeters - roomCenter.y); // Y in 2D is Z in 3D, and inverted
        
        return (
            <group key={obj.id} position={[x, height / 2, z]} onClick={() => onObjectClick(obj.id)}>
                <Box args={[width, height, depth]} >
                    <meshStandardMaterial 
                        color={obj.id === selectedObjectId ? 'yellow' : categories[obj.category]?.color || 'gray'} 
                        transparent 
                        opacity={0.8}
                    />
                </Box>
                 <DreiText position={[0, height / 2 + 0.3, 0]} color="white" fontSize={0.2} anchorX="center" anchorY="middle">
                    {obj.category} {obj.id.split('_')[1]}
                </DreiText>
            </group>
        );
    }), [objects, room, categories, pxToMeters, onObjectClick, selectedObjectId]);

    return (
        <Canvas camera={{ position: [0, 5, 10], fov: 60 }}>
            <ambientLight intensity={0.6} />
            <directionalLight position={[10, 10, 5]} intensity={1} />
            <gridHelper args={[room.width, room.width/2, 'gray', 'gray']} />
            <axesHelper args={[5]} />
            {objectMeshes}
            <OrbitControls />
        </Canvas>
    );
}

export default function Step3Visualize({ appState, setAppState, onNext, onBack, categories, pxToMeters, resetApp }) {
    const [selectedObjectId, setSelectedObjectId] = useState(null);
    const [finalConfig, setFinalConfig] = useState(null);

    const selectedObject = appState.objects.find(o => o.id === selectedObjectId);

    const handlePropertyChange = (propName, value) => {
        setAppState(prev => ({
            ...prev,
            objects: prev.objects.map(obj => 
                obj.id === selectedObjectId ? { ...obj, properties: { ...obj.properties, [propName]: value } } : obj
            )
        }));
    };
    
    const handleRunSimulation = async () => {
        // 1. Create the final JSON structure
        const racks = appState.objects
            .filter(o => o.category === 'Data Rack')
            .map(o => {
                const bbox = getBoundingBox(o.contour.points);
                return {
                    name: `rack_${o.id.split('_')[1]}`,
                    pos: [(bbox.x * pxToMeters), (bbox.y * pxToMeters), 0],
                    dims: [bbox.width * pxToMeters, bbox.height * pxToMeters, o.properties.height],
                    power_watts: o.properties.heat_load_btu * 0.293071, // Convert BTU/hr to Watts
                };
            });

        const cracs = appState.objects
            .filter(o => o.category === 'CRAC')
            .map(o => {
                const bbox = getBoundingBox(o.contour.points);
                return {
                    name: `crac_${o.id.split('_')[1]}`,
                    pos: [(bbox.x * pxToMeters), (bbox.y * pxToMeters), 0],
                    dims: [bbox.width * pxToMeters, bbox.height * pxToMeters, o.properties.height],
                    supply_velocity: 2.0, // Default value from your python script
                    supply_temp_K: o.properties.supply_temp_c + 273.15,
                };
            });
        
        const config = {
            room: { dims: [appState.room.width, appState.room.length, appState.room.height] },
            racks,
            cracs,
            physics: {
                crac_supply_temp_K: appState.objects
                    .find(o => o.category === 'CRAC')?.properties.supply_temp_c + 273.15 || 285.15,
            },
            // Add other physics/meshing params from your original script if needed
        };
        
        setFinalConfig(config);

        // 2. Send to backend
        try {
            const response = await apiClient.post('http://localhost:5000/api/run-simulation', config);
            console.log("received response")
            const { run_id } = response.data;

            // Store the runId and move to the next step
            setAppState(prev => ({ ...prev, runId: run_id }));
            onNext();
        } catch (error) {
            console.error("Failed to run simulation:", error);
        }
    };

    return (
        <Grid>
            <Grid.Col span={{ base: 12, md: 8 }}>
                <Paper shadow="md" withBorder style={{ height: '60vh' }}>
                    <ThreeDScene 
                        objects={appState.objects} 
                        room={appState.room} 
                        categories={categories}
                        pxToMeters={pxToMeters}
                        onObjectClick={setSelectedObjectId}
                        selectedObjectId={selectedObjectId}
                    />
                </Paper>
            </Grid.Col>
            <Grid.Col span={{ base: 12, md: 4 }}>
                <Paper shadow="md" p="xl" withBorder>
                    <Title order={4}>Room Properties</Title>
                    <SimpleGrid cols={3} mt="sm">
                       <NumberInput label="Width (m)" value={appState.room.width} onChange={v => setAppState(p=>({...p, room: {...p.room, width:v}}))} />
                       <NumberInput label="Length (m)" value={appState.room.length} onChange={v => setAppState(p=>({...p, room: {...p.room, length:v}}))} />
                       <NumberInput label="Height (m)" value={appState.room.height} onChange={v => setAppState(p=>({...p, room: {...p.room, height:v}}))} />
                    </SimpleGrid>

                    <Title order={4} mt="xl">Object Properties</Title>
                    <Text size="sm" c="dimmed">Click on an object in the 3D view to edit.</Text>

                    {selectedObject ? (
                        <div key={selectedObjectId}>
                            <Text weight={700} mt="md">{selectedObject.category} {selectedObject.id.split('_')[1]}</Text>
                               {Object.entries(selectedObject.properties).map(([key, value]) => (
                                    <NumberInput 
                                        key={key}
                                        label={key.replace(/_/g, ' ').replace('btu', '(BTU/hr)').replace(' c', ' (°C)')}
                                        value={value}
                                        onChange={(val) => handlePropertyChange(key, val)}
                                        precision={key === 'height' ? 2 : 0} // Better precision for different units
                                        step={key.includes('btu') ? 100 : 0.1}
                                        mt="xs"
                                    />
                                ))}
                        </div>
                    ) : (
                        <Text mt="md" c="dimmed" align="center">No object selected</Text>
                    )}
                    
                    <Group position="apart" mt="xl">
                        <Button variant="default" onClick={onBack}>Back</Button>
                        <Button color="green" onClick={handleRunSimulation}>Run Simulation</Button>
                    </Group>
                </Paper>
            </Grid.Col>
            
            {finalConfig && (
                <Grid.Col span={12}>
                    <Paper shadow="md" p="xl" withBorder>
                        <Title order={4}>Generated Simulation Config</Title>
                        <Text size="sm" c="dimmed" mb="md">This JSON is sent to the backend for the final simulation.</Text>
                        <ScrollArea style={{ height: 300 }}>
                            <Code block>{JSON.stringify(finalConfig, null, 2)}</Code>
                        </ScrollArea>
                         <Center mt="xl">
                            <Button onClick={resetApp} variant="light">Start Over</Button>
                        </Center>
                    </Paper>
                </Grid.Col>
            )}
        </Grid>
    );
}