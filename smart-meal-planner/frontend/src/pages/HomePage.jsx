import React from 'react';
import { Link } from 'react-router-dom';
import { ChefHat, ShoppingBag, DollarSign } from 'lucide-react';

const HomePage = () => {
  return (
    <div className="max-w-4xl mx-auto">
      <div className="text-center mb-12">
        <h1 className="text-4xl md:text-5xl font-bold text-gray-900 mb-6">
          Eat Healthy. <span className="text-primary-600">Save Money.</span><br />
          Shop Smarter.
        </h1>
        <p className="text-xl text-gray-600 mb-8 max-w-2xl mx-auto">
          Automatically discover grocery deals in Quebec, generate personalized meal plans,
          and save 20-40% on your weekly shopping bill.
        </p>

        <div className="flex justify-center gap-8 mb-12">
           <div className="flex flex-col items-center">
              <div className="bg-primary-100 p-3 rounded-full mb-2">
                 <DollarSign className="w-6 h-6 text-primary-600" />
              </div>
              <span className="font-medium">Find Best Deals</span>
           </div>
           <div className="flex flex-col items-center">
              <div className="bg-accent-100 p-3 rounded-full mb-2">
                 <ChefHat className="w-6 h-6 text-accent-600" />
              </div>
              <span className="font-medium">AI Meal Planning</span>
           </div>
           <div className="flex flex-col items-center">
              <div className="bg-blue-100 p-3 rounded-full mb-2">
                 <ShoppingBag className="w-6 h-6 text-blue-600" />
              </div>
              <span className="font-medium">Smart Lists</span>
           </div>
        </div>
      </div>

      <div className="text-center">
        <Link to="/register" className="bg-primary-600 text-white py-3 px-8 rounded-lg hover:bg-primary-700 font-bold text-lg shadow-md transition-transform transform hover:-translate-y-0.5">
            Get Started
        </Link>
        <p className="mt-4 text-gray-600">
            Already have an account? <Link to="/login" className="text-primary-600 hover:underline">Login</Link>
        </p>
      </div>
    </div>
  );
};

export default HomePage;
