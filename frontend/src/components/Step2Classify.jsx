// Step2Classify.jsx

import { useState, useRef, useEffect } from 'react';
import { Grid, Paper, Radio, Title, Button, Group, Text, Center, Loader, Box } from '@mantine/core';
import { aiClient } from '../api';

// Helper for point-in-polygon test
function isPointInPolygon(point, polygon) {
    if (!polygon || polygon.length === 0) return false;
    let x = point[0], y = point[1];
    let inside = false;
    for (let i = 0, j = polygon.length - 1; i < polygon.length; j = i++) {
        let xi = polygon[i][0], yi = polygon[i][1];
        let xj = polygon[j][0], yj = polygon[j][1];
        let intersect = ((yi > y) !== (yj > y)) && (x < (xj - xi) * (y - yi) / (yj - yi) + xi);
        if (intersect) inside = !inside;
    }
    return inside;
}

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


// MODIFIED: Canvas now supports hover/deselect on classified objects and displays them with bounding boxes.
function InteractiveCanvas({ imageSrc, unclassified, classified, onContourClick, categories, roomContour, hoveredContourId, setHoveredContourId }) {
    const canvasRef = useRef(null);

    useEffect(() => {
        const canvas = canvasRef.current;
        const ctx = canvas.getContext('2d');
        const img = new Image();
        img.src = imageSrc;
        img.onload = () => {
            canvas.width = img.width;
            canvas.height = img.height;
            ctx.clearRect(0, 0, canvas.width, canvas.height);
            ctx.drawImage(img, 0, 0);

            // Draw room contour
            if (roomContour) {
                ctx.strokeStyle = 'cyan';
                ctx.lineWidth = 4;
                ctx.lineJoin = 'round';
                ctx.beginPath();
                ctx.moveTo(roomContour.points[0][0], roomContour.points[0][1]);
                for (let i = 1; i < roomContour.points.length; i++) {
                    ctx.lineTo(roomContour.points[i][0], roomContour.points[i][1]);
                }
                ctx.closePath();
                ctx.stroke();
            }

            // Combine all items that can be hovered
            const allHoverableItems = [
                ...unclassified,
                ...classified.map(c => ({ id: c.id, points: c.contour.points }))
            ];
            
            // Draw hover effect if any item is hovered
            if (hoveredContourId) {
                const item = allHoverableItems.find(i => i.id === hoveredContourId);
                if (item) {
                    ctx.beginPath();
                    ctx.moveTo(item.points[0][0], item.points[0][1]);
                    for (let i = 1; i < item.points.length; i++) {
                        ctx.lineTo(item.points[i][0], item.points[i][1]);
                    }
                    ctx.closePath();
                    ctx.fillStyle = 'rgba(255, 0, 255, 0.4)'; // Semi-transparent magenta
                    ctx.fill();
                }
            }
            
            // Draw classified objects using their bounding box
            ctx.lineWidth = 2; // Thinner outlines for selected objects
            classified.forEach(obj => {
                ctx.strokeStyle = categories[obj.category]?.color || 'gray';
                const bbox = getBoundingBox(obj.contour.points);
                ctx.strokeRect(bbox.x, bbox.y, bbox.width, bbox.height);
            });
        };
    }, [imageSrc, unclassified, classified, categories, roomContour, hoveredContourId]);

    const getMousePos = (event) => {
        const canvas = canvasRef.current;
        const rect = canvas.getBoundingClientRect();
        const scaleX = canvas.width / rect.width;
        const scaleY = canvas.height / rect.height;
        const x = (event.clientX - rect.left) * scaleX;
        const y = (event.clientY - rect.top) * scaleY;
        return { x, y };
    }

    const handleMouseMove = (event) => {
        const { x, y } = getMousePos(event);
        // Check both unclassified and classified items for hover
        const allItems = [
            ...unclassified, 
            ...classified.map(c => ({ id: c.id, points: c.contour.points }))
        ];
        const hovered = allItems.find(c => isPointInPolygon([x, y], c.points));
        setHoveredContourId(hovered ? hovered.id : null);
    };
    
    const handleMouseLeave = () => {
        setHoveredContourId(null);
    }

    const handleClick = () => {
        if (hoveredContourId) {
            onContourClick(hoveredContourId);
        }
    };

    return <canvas ref={canvasRef} onClick={handleClick} onMouseMove={handleMouseMove} onMouseLeave={handleMouseLeave} style={{ maxWidth: '100%', cursor: 'pointer' }} />;
}


export default function Step2Classify({ appState, setAppState, onNext, onBack, categories }) {
    const [activeCategory, setActiveCategory] = useState(Object.keys(categories)[0]);
    const [loading, setLoading] = useState(false);
    const [hoveredContourId, setHoveredContourId] = useState(null); // State for hover highlight

    const handleContourClick = (contourId) => {
        // Check if the clicked item is already classified
        const classifiedIndex = appState.objects.findIndex(o => o.id === contourId);

        if (classifiedIndex > -1) {
            // It's a classified object -> Deselect it (move back to unclassified)
            const [objectToDeselect] = appState.objects.splice(classifiedIndex, 1);
            setAppState(prev => ({
                ...prev,
                objects: [...prev.objects], // The object is already removed via splice
                unclassifiedContours: [...prev.unclassifiedContours, objectToDeselect.contour],
            }));
        } else {
            // It's an unclassified contour -> Classify it
            const contourToClassify = appState.unclassifiedContours.find(c => c.id === contourId);
            if (!contourToClassify) return;

            setAppState(prev => ({
                ...prev,
                unclassifiedContours: prev.unclassifiedContours.filter(c => c.id !== contourId),
                objects: [...prev.objects, {
                    id: contourId,
                    category: activeCategory,
                    contour: contourToClassify,
                    properties: { ...categories[activeCategory].default_properties }
                }],
            }));
        }
    };
    
    const handleAutofill = async () => {
        setLoading(true);
        const example_objects = appState.objects.map(obj => ({
            category: obj.category,
            contour: obj.contour
        }));

        try {
            const response = await aiClient.post('/autofill', {
                image_b64: appState.image.b64,
                example_objects,
                unclassified_contours: appState.unclassifiedContours
            });
            
            const { newly_classified } = response.data;
            const newObjects = [];
            const stillUnclassified = [...appState.unclassifiedContours];

            newly_classified.forEach(item => {
                const contourIndex = stillUnclassified.findIndex(c => c.id === item.id);
                if (contourIndex > -1) {
                    const [contourToMove] = stillUnclassified.splice(contourIndex, 1);
                    newObjects.push({
                        id: item.id,
                        category: item.category,
                        contour: contourToMove,
                        properties: { ...categories[item.category].default_properties }
                    });
                }
            });

            setAppState(prev => ({
                ...prev,
                unclassifiedContours: stillUnclassified,
                objects: [...prev.objects, ...newObjects]
            }));

        } catch (error) {
            console.error("Autofill failed:", error);
        } finally {
            setLoading(false);
        }
    };

    const hasExamples = appState.objects.length > 0;
    const hasUnclassified = appState.unclassifiedContours.length > 0;

    return (
        <Grid>
            <Grid.Col span={{ base: 12, md: 8 }}>
                <Paper shadow="md" withBorder p="xs">
                   {appState.image.url && (
                        <InteractiveCanvas
                            imageSrc={appState.image.url}
                            unclassified={appState.unclassifiedContours}
                            classified={appState.objects}
                            onContourClick={handleContourClick}
                            categories={categories}
                            roomContour={appState.room.contour}
                            hoveredContourId={hoveredContourId}
                            setHoveredContourId={setHoveredContourId}
                        />
                   )}
                </Paper>
            </Grid.Col>
            <Grid.Col span={{ base: 12, md: 4 }}>
                <Paper shadow="md" p="xl" withBorder>
                    <Title order={4}>Classification</Title>
                    <Text size="sm" c="dimmed" mb="md">Select a category, then click on an object to classify it. Click a classified object to deselect it.</Text>
                    <Radio.Group value={activeCategory} onChange={setActiveCategory} name="categorySelector" label="Select category to assign">
                        <Group mt="xs">
                            {Object.keys(categories).map(cat => <Radio key={cat} value={cat} label={cat} />)}
                        </Group>
                    </Radio.Group>
                    
                    <Title order={4} mt="xl">AI Autofill</Title>
                     <Text size="sm" c="dimmed" mb="md">
                        {hasExamples ? "Use your selections to automatically classify the rest." : "First, classify at least one object manually."}
                    </Text>
                    <Button onClick={handleAutofill} disabled={!hasExamples || !hasUnclassified || loading} fullWidth>
                        {loading ? <Loader size="sm" color="white" /> : "Autofill Remaining Objects"}
                    </Button>
                    <Group position="apart" mt="xl">
                        <Button variant="default" onClick={onBack}>Back</Button>
                        <Button onClick={onNext} disabled={appState.objects.length === 0}>Next Step</Button>
                    </Group>
                </Paper>
            </Grid.Col>
        </Grid>
    );
}