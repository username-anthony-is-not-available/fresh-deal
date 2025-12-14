import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import NutritionDashboard from '../pages/NutritionDashboard';
import * as nutritionService from '../services/nutritionService';
import { vi } from 'vitest';

// Mock the nutritionService
vi.mock('../services/nutritionService');

const mockGoal = {
    goal_type: 'maintenance',
    target_calories: 2000,
    target_protein: 150,
    target_carbs: 250,
    target_fats: 70,
};

const mockSummary = [
    { date: '2023-01-01', calories: 1800, protein: 120, carbs: 200, fats: 60 },
    { date: '2023-01-02', calories: 2100, protein: 160, carbs: 260, fats: 75 },
];

describe('NutritionDashboard', () => {
    beforeEach(() => {
        nutritionService.getNutritionGoal.mockResolvedValue(mockGoal);
        nutritionService.getNutritionSummary.mockResolvedValue(mockSummary);
    });

    it('renders the dashboard title', async () => {
        render(
            <BrowserRouter>
                <NutritionDashboard />
            </BrowserRouter>
        );
        await waitFor(() => {
            expect(screen.getByText('Nutrition Dashboard')).toBeInTheDocument();
        });
    });

    it('displays loading state initially', () => {
        render(
            <BrowserRouter>
                <NutritionDashboard />
            </BrowserRouter>
        );
        expect(screen.getByText('Loading...')).toBeInTheDocument();
    });

    it('fetches and displays nutrition goals', async () => {
        render(
            <BrowserRouter>
                <NutritionDashboard />
            </BrowserRouter>
        );
        await waitFor(() => {
            expect(screen.getByText('Your Nutrition Goals (maintenance)')).toBeInTheDocument();
            expect(screen.getByText('Calories:')).toBeInTheDocument();
            expect(screen.getByText('2000 kcal')).toBeInTheDocument();
        });
    });

    it('fetches and displays nutrition summary chart', async () => {
        render(
            <BrowserRouter>
                <NutritionDashboard />
            </BrowserRouter>
        );
        await waitFor(() => {
            expect(screen.getByText('Last 7 Days Nutrition Summary')).toBeInTheDocument();
            // A simple way to check if the chart is there is to look for one of its labels
            expect(screen.getByText('Calories (kcal)')).toBeInTheDocument();
        });
    });

    it('handles API errors gracefully', async () => {
        nutritionService.getNutritionGoal.mockRejectedValue(new Error('API Error'));
        render(
            <BrowserRouter>
                <NutritionDashboard />
            </BrowserRouter>
        );
        await waitFor(() => {
            // Check that loading is finished but no data is displayed
            expect(screen.queryByText('Loading...')).not.toBeInTheDocument();
            expect(screen.queryByText('Your Nutrition Goals (maintenance)')).not.toBeInTheDocument();
        });
    });
});
