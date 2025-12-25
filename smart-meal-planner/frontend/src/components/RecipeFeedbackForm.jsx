import React, { useState } from 'react';
import api from '../services/api';
import { toast } from 'react-hot-toast';

const RecipeFeedbackForm = ({ recipeId }) => {
  const [status, setStatus] = useState('made_it');
  const [notes, setNotes] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      await api.post(`/recipes/${recipeId}/feedback`, { status, notes });
      toast.success('Feedback submitted!');
      // Reset form
      setStatus('made_it');
      setNotes('');
    } catch (error) {
      toast.error('Failed to submit feedback.');
      console.error('Feedback submission error:', error);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="mt-4 space-y-4">
      <div>
        <label htmlFor="status" className="block text-sm font-medium text-gray-700">
          Did you make this recipe?
        </label>
        <select
          id="status"
          value={status}
          onChange={(e) => setStatus(e.target.value)}
          className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
        >
          <option value="made_it">Made It</option>
          <option value="skipped">Skipped It</option>
        </select>
      </div>
      <div>
        <label htmlFor="notes" className="block text-sm font-medium text-gray-700">
          Notes
        </label>
        <textarea
          id="notes"
          rows={3}
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
          placeholder="What did you think?"
        />
      </div>
      <button
        type="submit"
        className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500"
      >
        Submit Feedback
      </button>
    </form>
  );
};

export default RecipeFeedbackForm;
