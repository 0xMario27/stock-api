import { createRouter, createWebHistory } from "vue-router";
import DashboardView from "@/views/DashboardView.vue";
import WatchlistView from "@/views/WatchlistView.vue";
import DetailView from "@/views/DetailView.vue";

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/", name: "dashboard", component: DashboardView },
    { path: "/watchlist", name: "watchlist", component: WatchlistView },
    { path: "/stock/:code", name: "detail", component: DetailView, props: (route) => ({ code: route.params.code as string, assetClass: (route.query.asset_class as string) || "stock" }) },
    { path: "/inspect/:code", name: "inspect", component: () => import("@/views/InspectView.vue"), props: (route) => ({ code: route.params.code as string, assetClass: (route.query.asset_class as string) || "stock" }) },
  ],
});
