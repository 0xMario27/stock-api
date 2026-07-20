import { createRouter, createWebHistory } from "vue-router";
import WatchlistView from "@/views/WatchlistView.vue";
import DetailView from "@/views/DetailView.vue";

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/", name: "watchlist", component: WatchlistView },
    { path: "/stock/:code", name: "detail", component: DetailView, props: true },
    { path: "/inspect/:code", name: "inspect", component: () => import("@/views/InspectView.vue"), props: true },
  ],
});
