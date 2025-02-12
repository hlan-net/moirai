import { shallowMount } from '@vue/test-utils';
import MainPage from '@/components/MainPage.vue';

describe('MainPage.vue', () => {
  it('renders correctly', () => {
    const wrapper = shallowMount(MainPage);
    expect(wrapper.exists()).toBe(true);
  });
});