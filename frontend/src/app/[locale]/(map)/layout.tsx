import MapShell from "@/components/MapShell";

/** Home and word pages share the header and the map, which stays mounted between words. */
export default function MapLayout({ children }: LayoutProps<"/[locale]">) {
  return <MapShell>{children}</MapShell>;
}
