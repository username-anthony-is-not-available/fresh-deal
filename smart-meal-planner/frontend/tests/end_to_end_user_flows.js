import axios from 'axios';

const BASE_URL = 'http://localhost:8000';
const API_URL = `${BASE_URL}/api`;

const testResults = [];
function record(name, passed, details = '') {
  testResults.push({ name, passed, details });
  const icon = passed ? '✅' : '❌';
  console.log(`${icon} [${passed ? 'PASS' : 'FAIL'}] ${name} ${details ? '(' + details + ')' : ''}`);
}

async function runAllFlows() {
  console.log('🚀 Starting Comprehensive End-to-End User Flow Tests...\n');
  const timestamp = Date.now();
  const testEmail = `user_${timestamp}@testmealplanner.com`;
  const testPassword = 'Password123!';
  let authToken = null;
  let userId = null;
  let authHeaders = {};

  // 1. REGISTRATION FLOW
  try {
    const regRes = await axios.post(`${BASE_URL}/auth/register`, {
      email: testEmail,
      password: testPassword,
      postal_code: 'H2X1Y4',
      household_size: 3,
      dietary_preferences: ['gluten_free']
    });
    userId = regRes.data.id;
    record('User Registration', !!userId && regRes.status === 200, `User ID: ${userId}`);
  } catch (err) {
    record('User Registration', false, err.response?.data?.detail || err.message);
  }

  // 2. LOGIN FLOW
  try {
    const params = new URLSearchParams();
    params.append('username', testEmail);
    params.append('password', testPassword);
    const loginRes = await axios.post(`${BASE_URL}/auth/login/access-token`, params, {
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' }
    });
    authToken = loginRes.data.access_token;
    authHeaders = { Authorization: `Bearer ${authToken}` };
    record('User Login & JWT Token Retrieval', !!authToken, `Token acquired`);
  } catch (err) {
    record('User Login & JWT Token Retrieval', false, err.response?.data?.detail || err.message);
  }

  // 3. USER PROFILE & SETTINGS FLOW
  try {
    const profileRes = await axios.get(`${API_URL}/users/${userId}`, { headers: authHeaders });
    const match = profileRes.data.email === testEmail;
    record('Get User Profile', match, `Email: ${profileRes.data.email}`);

    // Update settings
    const updateRes = await axios.patch(`${API_URL}/users/${userId}`, {
      household_size: 4,
      postal_code: 'H4T1V6',
      dietary_preferences: ['vegetarian', 'gluten_free'],
      allergies: ['peanuts']
    }, { headers: authHeaders });
    const updatedOk = updateRes.data.household_size === 4 && updateRes.data.postal_code === 'H4T1V6';
    record('Update User Settings', updatedOk, `Household size: ${updateRes.data.household_size}`);
  } catch (err) {
    record('User Profile & Settings', false, err.response?.data?.detail || err.message);
  }

  // 4. DEALS SEEDING & BROWSING FLOW
  try {
    const seedRes = await axios.post(`${API_URL}/data/seed`, {}, { headers: authHeaders });
    record('Seed Grocery Deals & Recipes', seedRes.status === 200, `Seeded successfully`);

    const dealsRes = await axios.get(`${API_URL}/deals?limit=20`, { headers: authHeaders });
    const count = Array.isArray(dealsRes.data) ? dealsRes.data.length : 0;
    record('Browse Grocery Deals', count > 0, `Retrieved ${count} deals`);

    // Filter deals by query
    const filterRes = await axios.get(`${API_URL}/deals?query=chicken&limit=10`, { headers: authHeaders });
    record('Search Deals by Query', Array.isArray(filterRes.data), `Query matches: ${filterRes.data.length}`);
  } catch (err) {
    record('Deals Seeding & Browsing', false, err.response?.data?.detail || err.message);
  }

  // 5. NUTRITION GOAL SETTING FLOW
  try {
    const setGoalRes = await axios.post(`${API_URL}/users/me/nutrition-goal`, {
      goal_type: 'muscle_gain',
      target_calories: 2500,
      target_protein: 160,
      target_carbs: 280,
      target_fats: 80
    }, { headers: authHeaders });
    record('Set Nutrition Goal', setGoalRes.status === 200, `Goal: muscle_gain`);

    const getGoalRes = await axios.get(`${API_URL}/users/me/nutrition-goal`, { headers: authHeaders });
    const goalOk = getGoalRes.data.target_calories === 2500;
    record('Retrieve Nutrition Goal', goalOk, `Target: ${getGoalRes.data.target_calories} kcal`);

    const summaryRes = await axios.get(`${API_URL}/users/me/nutrition-summary?start_date=2026-11-01&end_date=2026-11-08`, { headers: authHeaders });
    record('Retrieve Nutrition Summary', Array.isArray(summaryRes.data), `Summary records: ${summaryRes.data.length}`);
  } catch (err) {
    record('Nutrition Goal & Summary Flow', false, err.response?.data?.detail || err.message);
  }

  // 6. MEAL PLAN GENERATION FLOW
  let generatedPlan = null;
  try {
    const genRes = await axios.post(`${API_URL}/plans/generate?user_id=${userId}&model=gpt-4o-mini`, {}, { headers: authHeaders });
    const taskId = genRes.data.task_id;
    record('Trigger Meal Plan Generation', !!taskId, `Task ID: ${taskId}`);

    // Poll task status
    let finished = false;
    for (let i = 0; i < 30; i++) {
      const taskRes = await axios.get(`${API_URL}/tasks/${taskId}`, { headers: authHeaders });
      if (taskRes.data.status === 'SUCCESS' || taskRes.data.status === 'FAILED') {
        finished = true;
        record('Meal Plan Task Completion', taskRes.data.status === 'SUCCESS', `Status: ${taskRes.data.status}`);
        break;
      }
      await new Promise(r => setTimeout(r, 1000));
    }
    if (!finished) {
      record('Meal Plan Task Completion', false, 'Timed out waiting for task');
    }

    // Retrieve latest meal plan
    const latestRes = await axios.get(`${API_URL}/plans/${userId}/latest`, { headers: authHeaders });
    generatedPlan = latestRes.data;
    const days = generatedPlan?.meal_plan || generatedPlan?.days || [];
    const hasDays = days.length === 7;
    record('Retrieve Latest Meal Plan (7 Days)', hasDays, `Plan ID: ${generatedPlan?.id || 'none'}, Days: ${days.length}`);
  } catch (err) {
    record('Meal Plan Generation Flow', false, err.response?.data?.detail || err.message);
  }

  // 7. MEAL REGENERATION & FEEDBACK FLOW
  try {
    const regenRes = await axios.post(`${API_URL}/plans/regenerate-meal`, {
      user_id: userId,
      day: 'Monday',
      type: 'dinner',
      dietary_preferences: [],
      existing_meals: []
    }, { headers: authHeaders });
    record('Regenerate Single Meal', regenRes.status === 200 && !!regenRes.data.recipe_name, `New meal: ${regenRes.data.recipe_name}`);

    // Submit Feedback on Meal Plan
    if (generatedPlan?.id) {
      const fbRes = await axios.post(`${API_URL}/feedback`, {
        meal_plan_id: generatedPlan.id,
        rating: 5,
        comment: 'Great meal plan with high protein!'
      }, { headers: authHeaders });
      record('Submit Meal Plan Feedback', fbRes.status === 200 || fbRes.status === 201, `Rating 5 submitted`);
    }
  } catch (err) {
    record('Meal Regeneration & Feedback Flow', false, err.response?.data?.detail || err.message);
  }

  // 8. RECIPES & FAVORITES FLOW
  let sampleRecipeId = null;
  try {
    const recipesRes = await axios.get(`${API_URL}/recipes?limit=10`, { headers: authHeaders });
    const recipes = Array.isArray(recipesRes.data) ? recipesRes.data : [];
    record('Browse Recipes', recipes.length > 0, `Found ${recipes.length} recipes`);

    if (recipes.length > 0) {
      sampleRecipeId = recipes[0].id;

      // Recipe Details
      const detailRes = await axios.get(`${API_URL}/recipes/${sampleRecipeId}`, { headers: authHeaders });
      record('Get Recipe Detail', !!detailRes.data?.name, `Recipe: ${detailRes.data?.name}`);

      // Rate recipe
      const rateRes = await axios.post(`${API_URL}/recipes/${sampleRecipeId}/rate`, { rating: 5 }, { headers: authHeaders });
      record('Rate Recipe', rateRes.status === 200, `Rated 5 stars`);

      // Favorite recipe
      const favRes = await axios.post(`${API_URL}/recipes/${sampleRecipeId}/favorite`, {}, { headers: authHeaders });
      record('Add Recipe to Favorites', favRes.status === 200, `Recipe ${sampleRecipeId} favorited`);

      // View Favorites
      const myFavsRes = await axios.get(`${API_URL}/users/me/favorites`, { headers: authHeaders });
      const favList = Array.isArray(myFavsRes.data) ? myFavsRes.data : [];
      const isFavorited = favList.some(r => r.id === sampleRecipeId);
      record('View User Favorites', isFavorited, `Favorites count: ${favList.length}`);

      // Unfavorite
      const unfavRes = await axios.delete(`${API_URL}/recipes/${sampleRecipeId}/favorite`, { headers: authHeaders });
      record('Remove Recipe from Favorites', unfavRes.status === 200, `Unfavorited`);
    }
  } catch (err) {
    record('Recipes & Favorites Flow', false, err.response?.data?.detail || err.message);
  }

  // 9. SHOPPING LIST FLOW
  try {
    const shopRes = await axios.get(`${API_URL}/shopping/optimize?user_id=${userId}&strategy=min_cost`, { headers: authHeaders });
    const hasTotal = typeof shopRes.data.total_cost === 'number';
    record('Optimize Shopping List', hasTotal, `Total Cost: $${shopRes.data.total_cost}`);
  } catch (err) {
    record('Shopping List Flow', false, err.response?.data?.detail || err.message);
  }

  // 10. PANTRY MANAGEMENT FLOW
  let addedPantryItemId = null;
  try {
    const addPantryRes = await axios.post(`${API_URL}/pantry/${userId}/add`, {
      items: [
        { name: 'Olive Oil', quantity: 1, unit: 'bottle' },
        { name: 'Brown Rice', quantity: 2, unit: 'kg' }
      ]
    }, { headers: authHeaders });
    record('Add Items to Pantry', addPantryRes.status === 200, `Items added: ${addPantryRes.data.length}`);

    const getPantryRes = await axios.get(`${API_URL}/pantry/${userId}`, { headers: authHeaders });
    const items = Array.isArray(getPantryRes.data) ? getPantryRes.data : (getPantryRes.data?.items || []);
    record('Get Pantry Items', items.length > 0, `Pantry has ${items.length} items`);
    if (items.length > 0) {
      addedPantryItemId = items[0].id;
      // Delete single item
      const delRes = await axios.delete(`${API_URL}/pantry/${userId}/${addedPantryItemId}`, { headers: authHeaders });
      record('Delete Pantry Item', delRes.status === 200, `Deleted item ${addedPantryItemId}`);
    }

    // Consume Latest Plan from Pantry
    const consumeRes = await axios.post(`${API_URL}/pantry/${userId}/consume-latest-plan`, {}, { headers: authHeaders });
    record('Consume Plan from Pantry', consumeRes.status === 200, `Plan consumed`);
  } catch (err) {
    record('Pantry Management Flow', false, err.response?.data?.detail || err.message);
  }

  // 11. EXPORT MEAL PLAN (iCal & PDF)
  for (const fmt of ['ical', 'pdf']) {
    try {
      const expRes = await axios.get(`${API_URL}/plans/${userId}/export/${fmt}`, {
        headers: authHeaders,
        responseType: 'arraybuffer'
      });
      record(`Export Meal Plan (${fmt.toUpperCase()})`, expRes.status === 200 && expRes.data.length > 0, `Bytes: ${expRes.data.length}`);
    } catch (err) {
      record(`Export Meal Plan (${fmt.toUpperCase()})`, false, err.response?.data?.detail || err.message);
    }
  }

  // 12. SCRAPING DASHBOARD & HEALTH MONITORING
  try {
    const summaryRes = await axios.get(`${API_URL}/admin/scrapers/health/summary`, { headers: authHeaders });
    record('Scraper Health Summary', summaryRes.status === 200, `Status: ${summaryRes.data.overall_status}`);

    const metricsRes = await axios.get(`${API_URL}/admin/scrapers/health`, { headers: authHeaders });
    record('Scraper Health Metrics', Array.isArray(metricsRes.data), `Metrics count: ${metricsRes.data.length}`);

    const logsRes = await axios.get(`${API_URL}/admin/scrapers/logs?limit=10`, { headers: authHeaders });
    record('Scraper Audit Logs', Array.isArray(logsRes.data), `Logs count: ${logsRes.data.length}`);
  } catch (err) {
    record('Scraper Health & Monitoring Flow', false, err.response?.data?.detail || err.message);
  }

  // 13. FEEDBACK DASHBOARD FLOW
  try {
    const fbListRes = await axios.get(`${API_URL}/feedback`, { headers: authHeaders });
    record('Get Feedback List', Array.isArray(fbListRes.data), `Feedback count: ${fbListRes.data.length}`);

    const fbSummaryRes = await axios.get(`${API_URL}/feedback/summary`, { headers: authHeaders });
    record('Get Feedback Summary', fbSummaryRes.status === 200, `Avg rating: ${fbSummaryRes.data.average_rating || 'N/A'}`);
  } catch (err) {
    record('Feedback Dashboard Flow', false, err.response?.data?.detail || err.message);
  }

  // FINAL SUMMARY
  console.log('\n========================================');
  const total = testResults.length;
  const passed = testResults.filter(t => t.passed).length;
  const failed = total - passed;
  console.log(`TOTAL TESTS: ${total} | PASSED: ${passed} | FAILED: ${failed}`);
  console.log('========================================\n');

  if (failed > 0) {
    console.error('Some end-user flows failed! See details above.');
    process.exit(1);
  } else {
    console.log('🎉 ALL END-USER FLOWS PASSED SUCCESSFULLY!');
  }
}

runAllFlows();
