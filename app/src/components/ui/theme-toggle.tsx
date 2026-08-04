import { useEffect, useState } from "react";
import { Sun, Moon } from "lucide-react";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";

type Theme = "light" | "dark";

const ThemeToggle = () => {
  const [theme, setTheme] = useState<Theme>(() => {
    try {
      const savedTheme = localStorage.getItem("theme");
      // Normalize: only accept "light" or "dark", default to "dark"
      return (savedTheme === "light" || savedTheme === "dark") ? savedTheme : "dark";
    } catch {
      return "dark";
    }
  });

  useEffect(() => {
    const root = document.documentElement;
    root.setAttribute("data-theme", theme);
    try {
      localStorage.setItem("theme", theme);
    } catch (error) {
      console.warn("Failed to persist theme preference:", error);
    }
  }, [theme]);

  const toggleTheme = () => {
    setTheme((current) => (current === "dark" ? "light" : "dark"));
  };

  const getTooltipText = () => {
    return theme === "dark" ? "Switch to Light Mode" : "Switch to Dark Mode";
  };

  return (
    <TooltipProvider delayDuration={300} skipDelayDuration={0}>
      <Tooltip delayDuration={0}>
        <TooltipTrigger asChild>
          <button
            onClick={toggleTheme}
            className="relative flex items-center justify-between w-14 h-7 p-1 rounded-full bg-secondary/80 hover:bg-secondary border border-border/50 transition-colors focus:outline-none focus:ring-2 focus:ring-primary/20"
            aria-label="Toggle theme"
            data-testid="theme-toggle"
          >
            <Sun className={cn("h-3.5 w-3.5 z-10 transition-colors", theme === 'light' ? 'text-amber-500' : 'text-muted-foreground/50')} />
            <Moon className={cn("h-3.5 w-3.5 z-10 transition-colors", theme === 'dark' ? 'text-indigo-400' : 'text-muted-foreground/50')} />
            <div 
              className={cn(
                "absolute top-[3px] left-[3px] w-[22px] h-[22px] rounded-full bg-background shadow-sm transition-transform duration-300 ease-in-out flex items-center justify-center",
                theme === 'dark' ? 'translate-x-[26px]' : 'translate-x-0'
              )}
            >
              {theme === 'light' ? (
                <Sun className="h-3 w-3 text-amber-500" />
              ) : (
                <Moon className="h-3 w-3 text-indigo-400" />
              )}
            </div>
            <span className="sr-only">{getTooltipText()}</span>
          </button>
        </TooltipTrigger>
        <TooltipContent side="bottom">{getTooltipText()}</TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
};

export default ThemeToggle;
