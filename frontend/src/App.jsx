// App.jsx

// MODIFIED: Added useEffect
import { useState, useEffect } from 'react';
import { Stepper, Container, Title, Text, Center } from '@mantine/core';
import Step1Upload from './components/Step1Upload';
import Step2Classify from './components/Step2Classify';
import Step3Visualize from './components/Step3Visualize';
import Step4Results from './components/Step4Results';

// Constants for default object properties
const PIXELS_TO_METERS = 0.05; // Example conversion factor
const CATEGORIES = {
    "Data Rack": {
        color: "green",
        default_properties: { height: 2.2, heat_load_btu: 5000 }
    },
    "CRAC": {
        color: "blue",
        default_properties: { height: 1.8, supply_temp_c: 12.0, cooling_capacity_btu: 20000, power_consumption_kw: 10.0  }
    }
};

// ADDED: Bounding box helper function
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

export default function App() {
    const [activeStep, setActiveStep] = useState(0);
    const [appState, setAppState] = useState({
        image: { file: null, b64: null, url: null },
        unclassifiedContours: [], // {id, points}
        objects: [], // {id, category, contour, properties}
        // MODIFIED: Added contour field to room
        room: { width: 30, length: 30, height: 4, contour: null },
        runId: null,
    });

    // ADDED: useEffect to automatically calculate room dimensions
    useEffect(() => {
        if (appState.room.contour) {
            const bbox = getBoundingBox(appState.room.contour.points);
            const roomWidth = parseFloat((bbox.width * PIXELS_TO_METERS).toFixed(2));
            const roomLength = parseFloat((bbox.height * PIXELS_TO_METERS).toFixed(2));
            
            // Avoid infinite loops by checking if values actually changed
            if (appState.room.width !== roomWidth || appState.room.length !== roomLength) {
                 setAppState(prev => ({
                    ...prev,
                    room: {
                        ...prev.room,
                        width: roomWidth,
                        length: roomLength,
                    }
                }));
            }
        }
    }, [appState.room.contour]);


    const handleNextStep = () => setActiveStep((current) => (current < 3 ? current + 1 : current));
    const handlePrevStep = () => setActiveStep((current) => (current > 0 ? current - 1 : current));

    const resetToStep = (step) => {
        if (step === 0) {
            setAppState({
                image: { file: null, b64: null, url: null },
                unclassifiedContours: [],
                objects: [],
                // MODIFIED: Reset the room contour
                room: { width: 30, length: 30, height: 4, contour: null },
                runId: null, // Also reset the runId
            });
        }
        setActiveStep(step);
    };

    return (
        <Container size="xl" my="xl">
            <Center>
                <Title order={1}>CFD Floor Plan Automation</Title>
            </Center>
            <Center>
                <Text c="dimmed" mb="xl">From image to simulation-ready 3D model.</Text>
            </Center>

            <Stepper active={activeStep} onStepClick={setActiveStep} breakpoint="sm" allowNextStepsSelect={false}>
                <Stepper.Step label="Upload" description="Provide floor plan">
                    <Step1Upload setAppState={setAppState} onNext={handleNextStep} />
                </Stepper.Step>
                <Stepper.Step label="Classify" description="Identify objects">
                    <Step2Classify appState={appState} setAppState={setAppState} onNext={handleNextStep} onBack={handlePrevStep} categories={CATEGORIES} />
                </Stepper.Step>
                <Stepper.Step label="Visualize & Edit" description="Create 3D model">
                   <Step3Visualize appState={appState} setAppState={setAppState} onNext={handleNextStep} onBack={handlePrevStep} categories={CATEGORIES} pxToMeters={PIXELS_TO_METERS} resetApp={() => resetToStep(0)} />
                </Stepper.Step>
                <Stepper.Step label="Results" description="View simulation">
                    <Step4Results appState={appState} setAppState={setAppState} onReset={() => resetToStep(0)} />
                </Stepper.Step>
                <Stepper.Completed>
                    <Center>
                        <Text>Simulation request sent! Check backend console.</Text>
                    </Center>
                </Stepper.Completed>
            </Stepper>
        </Container>
    );
}