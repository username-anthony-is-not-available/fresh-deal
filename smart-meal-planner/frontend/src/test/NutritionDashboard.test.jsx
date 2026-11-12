import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import NutritionDashboard from '../pages/NutritionDashboard';
import * as nutritionService from '../services/nutritionService';
import { describe, it, expect, vi, beforeEach } from 'vitest';

// Mock the nutritionService
vi.mock('../services/nutritionService');

const mockGoal = {
    goal_type: 'maintenance',
    target_calories: 2000,
    target_protein: 150,
    target_carbs: 250,
    target_fats: 70,
    target_fiber: 30,
};

const mockSummary = [
    { date: '2023-01-01', calories: 1800, protein: 120, carbs: 200, fats: 60, fiber: 24 },
    { date: '2023-01-02', calories: 2100, protein: 160, carbs: 260, fats: 75, fiber: 32 },
];

const mockCompliance = {
    compliance_score: 85,
    status: 'compliant',
    restrictions: ['vegan', 'gluten-free'],
    warnings: [],
    micronutrients_to_watch: ['vitamin_b12', 'iron'],
};

describe('NutritionDashboard', () => {
    beforeEach(() => {
        nutritionService.getNutritionGoal.mockResolvedValue(mockGoal);
        nutritionService.getNutritionSummary.mockResolvedValue(mockSummary);
        nutritionService.getNutritionCompliance.mockResolvedValue(mockCompliance);
    });

    it('renders the dashboard title', async () => {
        render(
            <BrowserRouter>
                <NutritionDashboard />
            </BrowserRouter>
        );
        await waitFor(() => {
            expect(screen.getByText(/Nutritional Dashboard/i)).toBeInTheDocument();
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
            expect(screen.getByText(/Target: 2000 kcal/i)).toBeInTheDocument();
            expect(screen.getByText(/Target: 150 g/i)).toBeInTheDocument();
        });
    });

    it('fetches and displays nutrition summary chart', async () => {
        render(
            <BrowserRouter>
                <NutritionDashboard />
            </BrowserRouter>
        );
        await waitFor(() => {
            expect(screen.getByText(/Daily Macro Intake/i)).toBeInTheDocument();
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
            expect(screen.queryByText('Loading...')).not.toBeInTheDocument();
            expect(screen.queryByText(/Target: 2000 kcal/i)).not.toBeInTheDocument();
        });
    });

    it('displays dietary restriction compliance and fiber target', async () => {
        render(
            <BrowserRouter>
                <NutritionDashboard />
            </BrowserRouter>
        );
        await waitFor(() => {
            expect(screen.getByText(/Dietary Restriction Tracking/i)).toBeInTheDocument();
            expect(screen.getByText(/Score: 85\/100/i)).toBeInTheDocument();
            expect(screen.getByText(/Target: 30 g/i)).toBeInTheDocument();
            expect(screen.getByText(/vitamin b12/i)).toBeInTheDocument();
        });
    });
});