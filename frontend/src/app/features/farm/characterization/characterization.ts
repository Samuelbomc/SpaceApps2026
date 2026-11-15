import { Component } from '@angular/core';
import { FarmManage } from '../manage/manage';
@Component({
  selector: 'app-characterization',
  imports: [FarmManage],
  template: '<app-farm-manage />',
})
export class Characterization {}
