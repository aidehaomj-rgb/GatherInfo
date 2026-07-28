import { createElement } from "react";
const icon = (name) => (props) => createElement("svg", { ...props, "data-icon": name });
export const Check = icon("check");
export const ChevronDown = icon("chevron-down");
export const ChevronsDownUp = icon("chevrons-down-up");
export const ChevronsUpDown = icon("chevrons-up-down");
export const Search = icon("search");
export const X = icon("x");
