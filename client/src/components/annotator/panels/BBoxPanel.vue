<template>
  <div v-show="bbox.isActive">
    <PanelButton name="Delete BBox" @click="bbox.deleteBbox" />
    <PanelToggle name="Auto Select Color" v-model:value="bbox.color.auto" />
    <PanelToggle
      v-show="bbox.color.auto"
      name="Only Black or White"
      v-model:value="bbox.color.blackOrWhite"
    />
    <PanelInputString
      name="Stroke Color"
      v-model:value="bbox.polygon.pathOptions.strokeColor"
    />
  </div>
</template>

<script>
import PanelButton from "@/components/PanelButton.vue";
import PanelToggle from "@/components/PanelToggle.vue";
import PanelInputString from "@/components/PanelInputString.vue";

export default {
  name: "BBoxPanel",
  components: { PanelButton, PanelToggle, PanelInputString },
  props: {
    bbox: {
      type: Object,
      required: true
    }
  }
};
</script>
