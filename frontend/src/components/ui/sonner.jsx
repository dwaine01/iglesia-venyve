import { useEffect, useState } from "react"
import { useTheme } from "next-themes"
import { Toaster as Sonner, toast } from "sonner"

const MOBILE_TOAST_QUERY = "(max-width: 767px)"

const getInitialMobileState = () =>
  typeof window !== "undefined" && window.matchMedia(MOBILE_TOAST_QUERY).matches

const getResponsiveToastPosition = (position, isMobile) =>
  isMobile ? "bottom-center" : position

const Toaster = ({
  position = "top-right",
  style,
  ...props
}) => {
  const { theme = "system" } = useTheme()
  const [isMobile, setIsMobile] = useState(getInitialMobileState)

  useEffect(() => {
    const mediaQuery = window.matchMedia(MOBILE_TOAST_QUERY)
    const updateMobileState = (event) => setIsMobile(event.matches)
    setIsMobile(mediaQuery.matches)
    mediaQuery.addEventListener("change", updateMobileState)
    return () => mediaQuery.removeEventListener("change", updateMobileState)
  }, [])

  return (
    <Sonner
      theme={theme}
      position={getResponsiveToastPosition(position, isMobile)}
      className="toaster group"
      data-testid="global-toast-region"
      style={{
        ...style,
        ...(isMobile ? { width: "calc(100vw - 2rem)" } : {}),
      }}
      toastOptions={{
        classNames: {
          toast:
            "group toast group-[.toaster]:bg-background group-[.toaster]:text-foreground group-[.toaster]:border-border group-[.toaster]:shadow-lg",
          description: "group-[.toast]:text-muted-foreground",
          actionButton:
            "group-[.toast]:bg-primary group-[.toast]:text-primary-foreground",
          cancelButton:
            "group-[.toast]:bg-muted group-[.toast]:text-muted-foreground",
        },
      }}
      {...props} />
  );
}

export { Toaster, getResponsiveToastPosition, toast }
