import { useQuery } from "@tanstack/react-query";
import { catalogService } from "../../services/catalog.service";
import type { InputLookups } from "./input-management.types";

export function useInputLookups() {
  const terms = useQuery({ queryKey: ["terms"], queryFn: catalogService.terms });
  const faculties = useQuery({ queryKey: ["faculties"], queryFn: catalogService.faculties });
  const programs = useQuery({ queryKey: ["programs"], queryFn: catalogService.programs });
  const semesters = useQuery({ queryKey: ["semesters"], queryFn: catalogService.semesters });
  const courses = useQuery({ queryKey: ["courses"], queryFn: catalogService.courses });
  const curricula = useQuery({ queryKey: ["curricula"], queryFn: catalogService.curricula });
  const rooms = useQuery({ queryKey: ["rooms"], queryFn: catalogService.rooms });
  const staff = useQuery({ queryKey: ["staff"], queryFn: catalogService.staff });
  const groups = useQuery({ queryKey: ["groups"], queryFn: () => catalogService.groups() });
  const profiles = useQuery({ queryKey: ["profiles"], queryFn: catalogService.profiles });
  const offerings = useQuery({ queryKey: ["offerings"], queryFn: () => catalogService.offerings() });

  const queries = [
    terms,
    faculties,
    programs,
    semesters,
    courses,
    curricula,
    rooms,
    staff,
    groups,
    profiles,
    offerings,
  ];

  const data: InputLookups = {
    terms: terms.data ?? [],
    faculties: faculties.data ?? [],
    programs: programs.data ?? [],
    semesters: semesters.data ?? [],
    courses: courses.data ?? [],
    curricula: curricula.data ?? [],
    rooms: rooms.data ?? [],
    staff: staff.data ?? [],
    groups: groups.data ?? [],
    profiles: profiles.data ?? [],
    offerings: offerings.data ?? [],
  };

  return {
    data,
    isLoading: queries.some((query) => query.isLoading),
    error: queries.find((query) => query.error)?.error ?? null,
  };
}
