import { useContext } from 'react';
import { ThemeContext } from '../context/ThemeContext';
import { Sun, Moon } from 'lucide-react';

const ThemeToggle = () => {
  const { theme, toggleTheme } = useContext(ThemeContext);

  return (
    <button onClick={toggleTheme} className="p-2 rounded-full focus:outline-none text-gray-500 dark:text-gray-400">
      {theme === 'light' ? <Moon className="h-6 w-6" /> : <Sun className="h-6 w-6" />}
    </button>
  );
};

export default ThemeToggle;
