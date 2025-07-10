import { useState, useRef, useEffect } from 'react';
import { Grid, Paper, Radio, Title, Button, Group, Text, Center, Loader, Box } from '@mantine/core';
import axios from 'axios';
import apiClient from '../api';

// Helper for point-in-polygon test
function isPointInPolygon(point, polygon) {
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

function InteractiveCanvas({ imageSrc, unclassified, classified, onContourClick, categories, roomContour }) {
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

            // Draw unclassified contours
            if (roomContour) {
                ctx.strokeStyle = 'cyan'; // A distinct color for the room
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

            ctx.strokeStyle = 'magenta';
            ctx.lineWidth = 2;
            unclassified.forEach(({ points }) => {
                ctx.beginPath();
                ctx.moveTo(points[0][0], points[0][1]);
                for (let i = 1; i < points.length; i++) {
                    ctx.lineTo(points[i][0], points[i][1]);
                }
                ctx.closePath();
                ctx.stroke();
            });

            // Draw classified objects
            ctx.lineWidth = 3;
            classified.forEach(obj => {
                ctx.strokeStyle = categories[obj.category]?.color || 'gray';
                const { points } = obj.contour;
                ctx.beginPath();
                ctx.moveTo(points[0][0], points[0][1]);
                for (let i = 1; i < points.length; i++) {
                    ctx.lineTo(points[i][0], points[i][1]);
                }
                ctx.closePath();
                ctx.stroke();
            });
        };
    }, [imageSrc, unclassified, classified, categories, roomContour]);

    const handleClick = (event) => {
        const canvas = canvasRef.current;
        const rect = canvas.getBoundingClientRect();
        const scaleX = canvas.width / rect.width;
        const scaleY = canvas.height / rect.height;
        const x = (event.clientX - rect.left) * scaleX;
        const y = (event.clientY - rect.top) * scaleY;

        // Find which unclassified contour was clicked
        const clickedContour = unclassified.find(c => isPointInPolygon([x, y], c.points));
        if (clickedContour) {
            onContourClick(clickedContour.id);
        }
    };

    return <canvas ref={canvasRef} onClick={handleClick} style={{ maxWidth: '100%', cursor: 'pointer' }} />;
}


export default function Step2Classify({ appState, setAppState, onNext, onBack, categories }) {
    const [activeCategory, setActiveCategory] = useState(Object.keys(categories)[0]);
    const [loading, setLoading] = useState(false);

    const handleContourClick = (contourId) => {
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
    };
    
    const handleAutofill = async () => {
        setLoading(true);
        const example_objects = appState.objects.map(obj => ({
            category: obj.category,
            contour: obj.contour
        }));

        try {
            const response = await apiClient.post('http://localhost:5000/api/autofill', {
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
                        />
                   )}
                </Paper>
            </Grid.Col>
            <Grid.Col span={{ base: 12, md: 4 }}>
                <Paper shadow="md" p="xl" withBorder>
                    <Title order={4}>Classification</Title>
                    <Text size="sm" c="dimmed" mb="md">Select a category, then click on an unclassified object (magenta) in the image.</Text>
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