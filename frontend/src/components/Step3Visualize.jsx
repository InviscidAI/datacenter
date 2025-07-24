// components/Step3Visualize.jsx

import { useState, useMemo } from 'react';
import { Grid, Paper, Title, Button, Group, Text, NumberInput, Select, SimpleGrid } from '@mantine/core';
import { Canvas } from '@react-three/fiber';
import { OrbitControls, Box, Text as DreiText } from '@react-three/drei';
import { simClient } from '../api';

// Helper to calculate bounding box from contour points
function getBoundingBox(points) {
    let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
    if (!points || points.length === 0) return { x: 0, y: 0, width: 0, height: 0 };
    points.forEach(([x, y]) => {
        minX = Math.min(minX, x);
        minY = Math.min(minY, y);
        maxX = Math.max(maxX, x);
        maxY = Math.max(maxY, y);
    });
    return { x: minX, y: minY, width: maxX - minX, height: maxY - minY };
}

export function ThreeDScene({ objects, room, categories, pxToMeters, onObjectClick, selectedObjectId, roomContour }) {
    const roomCenterMeters = { x: room.width / 2, y: room.length / 2 };
    const roomOriginPx = useMemo(() => {
        if (!roomContour) return { x: 0, y: 0, width: 0, height: 0 };
        return getBoundingBox(roomContour.points);
    }, [roomContour]);

    const objectMeshes = useMemo(() => objects.map(obj => {
        let width, depth, x, z;
        const height = obj.properties?.height || 2.0;
        const uniqueKey = obj.id || obj.name;

        if (obj.contour && obj.contour.points) {
            const bbox = getBoundingBox(obj.contour.points);
            width = bbox.width * pxToMeters;
            depth = bbox.height * pxToMeters;
            
            const objCenterX_px = bbox.x + bbox.width / 2;
            const objCenterY_px = bbox.y + bbox.height / 2;
            
            const relativeX_px = objCenterX_px - roomOriginPx.x;
            const relativeY_px = objCenterY_px - roomOriginPx.y;

            x = relativeX_px * pxToMeters - roomCenterMeters.x;
            // --- FIX: Flipped Z-axis calculation to match floorplan orientation.
            // The top of the 2D image (smaller Y) should be further away (negative Z).
            z = (relativeY_px * pxToMeters) - roomCenterMeters.y;
        } 
        else if (obj.pos && obj.dims) {
            width = obj.dims[0];
            depth = obj.dims[1];
            
            const centerX = obj.pos[0] + width / 2;
            const centerZ = obj.pos[1] + depth / 2;

            x = centerX - roomCenterMeters.x;
            // --- FIX: Flipped Z-axis calculation for consistency.
            z = centerZ - roomCenterMeters.y; 
        } 
        else {
            console.error("Cannot render object, it is missing 'contour' or 'pos/dims':", obj);
            return null;
        }
        
        return (
            <group key={uniqueKey} position={[x, height / 2, z]} onClick={() => onObjectClick(uniqueKey)}>
                <Box args={[width, height, depth]} >
                    <meshStandardMaterial 
                        color={uniqueKey === selectedObjectId ? 'yellow' : categories[obj.category]?.color || 'gray'} 
                        transparent 
                        opacity={0.8}
                    />
                </Box>
                <DreiText position={[0, height / 2 + 0.3, 0]} color="black" fontSize={0.2} anchorX="center" anchorY="middle">
                    {obj.category} {(uniqueKey.split('_')[1] || '').substring(0, 4)}
                </DreiText>
            </group>
        );
    }), [objects, room, categories, pxToMeters, onObjectClick, selectedObjectId, roomOriginPx, roomCenterMeters]);

    return (
        <Canvas camera={{ position: [0, 5, 10], fov: 60 }}>
            <ambientLight intensity={0.6} />
            <directionalLight position={[10, 10, 5]} intensity={1} />
            <gridHelper args={[room.width, Math.floor(room.width/2), 'gray', 'gray']} />
            <axesHelper args={[5]} />
            {objectMeshes}
            <OrbitControls />
        </Canvas>
    );
}

export function PropertyEditor({ object, onPropertyChange }) {
    if (!object) {
        return <Text mt="md" c="dimmed" align="center">No object selected</Text>;
    }
    
    const faceOptions = ['x_min', 'x_max', 'y_min', 'y_max', 'z_min', 'z_max'];
    const objectKey = object.id || object.name;

    return (
        <div key={objectKey}>
            <Text weight={700} mt="md">{object.category} {objectKey.split('_')[1]}</Text>
            {Object.entries(object.properties).map(([key, value]) => {
                const label = key.replace(/_/g, ' ');
                if (key.includes('face')) {
                    return (
                        <Select
                            key={key}
                            label={label}
                            value={String(value)}
                            onChange={(val) => onPropertyChange(key, val)}
                            data={faceOptions}
                            mt="xs"
                        />
                    );
                }
                if (typeof value === 'number') {
                    return (
                        <NumberInput
                            key={key}
                            label={label}
                            value={Number(value)}
                            onChange={(val) => onPropertyChange(key, val)}
                            precision={3}
                            step={0.1}
                            mt="xs"
                        />
                    );
                }
                return <Text key={key}>{label}: {String(value)}</Text>;
            })}
        </div>
    );
}

export default function Step3Visualize({ appState, setAppState, onNext, onBack, categories, pxToMeters, generateConfig }) {
    const [selectedObjectId, setSelectedObjectId] = useState(null);

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
        const config = generateConfig(appState.objects, appState.room);
        
        try {
            const response = await simClient.post('/run-simulation', config);
            const { run_id } = response.data;

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
                        roomContour={appState.room.contour}
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

                    <PropertyEditor
                        object={selectedObject}
                        onPropertyChange={handlePropertyChange}
                    />
                    
                    <Group position="apart" mt="xl">
                        <Button variant="default" onClick={onBack}>Back</Button>
                        <Button color="green" onClick={handleRunSimulation}>Run Simulation</Button>
                    </Group>
                </Paper>
            </Grid.Col>
        </Grid>
    );
}