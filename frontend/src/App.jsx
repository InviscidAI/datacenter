// App.jsx

import { useState, useEffect } from 'react';
import { Stepper, Container, Title, Text, Center, Tabs } from '@mantine/core';
import Step1Upload from './components/Step1Upload';
import Step2Classify from './components/Step2Classify';
import Step3Visualize from './components/Step3Visualize';
import Step4Results from './components/Step4Results';
import StepOptimization from './components/StepOptimization';

const PIXELS_TO_METERS = 0.05;
const CATEGORIES = {
    "Data Rack": {
        color: "#43d270",
        default_properties: { height: 2.2, power_watts: 1000, flow_rate: 0.05, inlet_face: "x_max", outlet_face: "x_min" }
    },
    "CRAC": {
        color: "#ab9eff",
        // --- FIX: Added inlet/outlet face properties as requested.
        default_properties: { height: 1.8, supply_temp_K: 294.15, flow_rate: 8, inlet_face: "z_max", outlet_face: "y_min" }
    },
    "Perforated Tile": {
        color: "#f96c30",
        default_properties: { height: 0.01 }
    }
};

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
    const [activeTab, setActiveTab] = useState('setup');
    const [activeStep, setActiveStep] = useState(0);
    const [appState, setAppState] = useState({
        image: { file: null, b64: null, url: null },
        unclassifiedContours: [],
        objects: [],
        room: { width: 30, length: 30, height: 4, contour: null },
        runId: null,
        whatIfRunId: null
    });

    useEffect(() => {
        if (appState.room.contour) {
            const bbox = getBoundingBox(appState.room.contour.points);
            const roomWidth = parseFloat((bbox.width * PIXELS_TO_METERS).toFixed(2));
            const roomLength = parseFloat((bbox.height * PIXELS_TO_METERS).toFixed(2));
            if (appState.room.width !== roomWidth || appState.room.length !== roomLength) {
                 setAppState(prev => ({ ...prev, room: { ...prev.room, width: roomWidth, length: roomLength }}));
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
                room: { width: 30, length: 30, height: 4, contour: null },
                runId: null, whatIfRunId: null,
            });
        }
        setActiveStep(step);
    };

    const generateSimulationConfig = (objects, room) => {
        const roomBbox = room.contour ? getBoundingBox(room.contour.points) : { x: 0, y: 0 };
        
        const getSimObjects = (category, type) => {
            return objects
                .filter(o => o.category === category)
                .map(o => {
                    const simObject = { name: `${type}_${o.id.split('_')[1]}`, ...o.properties };

                    if (o.pos && o.dims) {
                        simObject.pos = o.pos;
                        simObject.dims = o.dims;
                    } else { 
                        const bbox = getBoundingBox(o.contour.points);
                        simObject.pos = [(bbox.x - roomBbox.x) * PIXELS_TO_METERS, (bbox.y - roomBbox.y) * PIXELS_TO_METERS, 0];
                        simObject.dims = [bbox.width * PIXELS_TO_METERS, bbox.height * PIXELS_TO_METERS, o.properties.height];
                    }
                    return simObject;
                });
        };

        return {
            room: { dims: [room.width, room.length, room.height] },
            racks: getSimObjects("Data Rack", "rack"),
            cracs: getSimObjects("CRAC", "crac"),
            tiles: getSimObjects("Perforated Tile", "tile"),
            physics: {
                crac_supply_temp_K: objects.find(o => o.category === "CRAC")?.properties.supply_temp_K || 285.15,
            },
        };
    };

    return (
        <Container size="xl" my="xl">
            <Center><Title order={1}>CFD Floor Plan Automation</Title></Center>
            <Center><Text c="dimmed" mb="xl">From image to simulation-ready 3D model and beyond.</Text></Center>
            <Tabs value={activeTab} onChange={setActiveTab}>
                <Tabs.List grow>
                    <Tabs.Tab value="setup">Design & Simulate</Tabs.Tab>
                    <Tabs.Tab value="optimize" disabled={!appState.runId}>Optimize</Tabs.Tab>
                    <Tabs.Tab value="results" disabled={!appState.runId}>Results & What-If</Tabs.Tab>
                </Tabs.List>
                <Tabs.Panel value="setup" pt="xl">
                    <Stepper active={activeStep} onStepClick={setActiveStep} breakpoint="sm" allowNextStepsSelect={false}>
                        <Stepper.Step label="Upload" description="Provide floor plan"><Step1Upload setAppState={setAppState} onNext={handleNextStep} /></Stepper.Step>
                        <Stepper.Step label="Classify" description="Identify objects"><Step2Classify appState={appState} setAppState={setAppState} onNext={handleNextStep} onBack={handlePrevStep} categories={CATEGORIES} /></Stepper.Step>
                        <Stepper.Step label="Visualize & Edit" description="Create 3D model"><Step3Visualize appState={appState} setAppState={setAppState} onNext={() => { handleNextStep(); setActiveTab('results'); }} onBack={handlePrevStep} categories={CATEGORIES} pxToMeters={PIXELS_TO_METERS} generateConfig={generateSimulationConfig} /></Stepper.Step>
                    </Stepper>
                </Tabs.Panel>
                <Tabs.Panel value="optimize" pt="xl"><StepOptimization appState={appState} generateConfig={generateSimulationConfig} /></Tabs.Panel>
                <Tabs.Panel value="results" pt="xl"><Step4Results appState={appState} setAppState={setAppState} onReset={() => { resetToStep(0); setActiveTab('setup'); }} generateConfig={generateSimulationConfig} categories={CATEGORIES} pxToMeters={PIXELS_TO_METERS} /></Tabs.Panel>
            </Tabs>
        </Container>
    );
}