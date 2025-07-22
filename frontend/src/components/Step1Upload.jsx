import { useState } from 'react';
import { Group, Button, Text, Paper, Center, Loader } from '@mantine/core';
import { IconUpload, IconFile } from '@tabler/icons-react';
import axios from 'axios';
import apiClient from '../api';

export default function Step1Upload({ setAppState, onNext }) {
    const [file, setFile] = useState(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState('');

    const handleFileChange = (e) => {
        const selectedFile = e.target.files[0];
        if (selectedFile) {
            setFile(selectedFile);
            setError('');
        }
    };

    const handleUpload = async () => {
        if (!file) {
            setError('Please select a file first.');
            return;
        }
        setLoading(true);
        setError('');

        const formData = new FormData();
        formData.append('file', file);

        try {
            const response = await apiClient.post('/process-image', formData, {
                headers: { 'Content-Type': 'multipart/form-data' },
            });
            const { image_b64, contours, room_contour } = response.data;
        
            // MODIFIED: Set the room contour in the app state
            setAppState(prev => ({
                ...prev,
                image: { file, b64: image_b64, url: URL.createObjectURL(file) },
                unclassifiedContours: contours,
                room: { ...prev.room, contour: room_contour }
            }));
            onNext();
        } catch (err) {
            setError('Failed to process image. Please check the backend.');
            console.error(err);
        } finally {
            setLoading(false);
        }
    };

    return (
        <Paper shadow="md" p="xl" withBorder>
            <Center style={{ flexDirection: 'column' }}>
                <input type="file" id="file-upload" style={{ display: 'none' }} onChange={handleFileChange} accept="image/*"/>
                <Button component="label" htmlFor="file-upload" leftIcon={<IconUpload size={16}/>} mb="md">
                    Select Floor Plan Image
                </Button>
                {file && <Text size="sm" c="dimmed"><IconFile size={14} /> {file.name}</Text>}
                {error && <Text color="red" size="sm" mt="sm">{error}</Text>}
                <Button onClick={handleUpload} disabled={!file || loading} mt="xl" mb="md">
                    {loading ? <Loader size="sm" color="white" /> : "Process Image & Continue"}
                </Button>
            </Center>
        </Paper>
    );
}