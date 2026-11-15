import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  ElementRef,
  Injector,
  afterNextRender,
  inject,
  input,
  output,
  signal,
  viewChild,
} from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { NavigationEnd, Router, RouterLink } from '@angular/router';
import { filter } from 'rxjs';
import { NavGroup } from '../navigation';

let nextId = 0;

/**
 * Navigation dropdown (disclosure pattern: a button that shows a list of links).
 *
 * - Mouse: opens on hover, closes when the pointer leaves (short grace delay).
 * - Click/tap/Enter/Space on the button toggles it (touch devices have no hover).
 * - ArrowDown opens and focuses the first link; Escape closes and returns focus;
 *   tabbing out closes it. Any navigation closes it.
 * - Inside the mobile menu it renders inline (CSS), still toggled by the button.
 */
@Component({
  selector: 'app-nav-dropdown',
  imports: [RouterLink],
  templateUrl: './nav-dropdown.html',
  styleUrl: './nav-dropdown.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: {
    '(mouseenter)': 'onPointerEnter()',
    '(mouseleave)': 'onPointerLeave()',
    '(focusout)': 'onFocusOut()',
    '(keydown.escape)': 'closeAndFocus($event)',
  },
})
export class NavDropdown {
  readonly group = input.required<NavGroup>();
  /** Emitted after a link is chosen (lets the header close the mobile menu). */
  readonly navigated = output<void>();

  private readonly host = inject<ElementRef<HTMLElement>>(ElementRef);
  private readonly injector = inject(Injector);
  private readonly trigger = viewChild.required<ElementRef<HTMLButtonElement>>('trigger');

  protected readonly menuId = `nav-dropdown-${nextId++}`;
  protected readonly open = signal(false);
  private openedBy: 'hover' | 'click' | null = null;
  private leaveTimer?: ReturnType<typeof setTimeout>;
  private readonly canHover =
    typeof matchMedia === 'function' && matchMedia('(hover: hover) and (pointer: fine)').matches;

  constructor() {
    inject(Router)
      .events.pipe(
        filter((e) => e instanceof NavigationEnd),
        takeUntilDestroyed(),
      )
      .subscribe(() => this.close());
    inject(DestroyRef).onDestroy(() => clearTimeout(this.leaveTimer));
  }

  protected toggle(): void {
    if (this.open() && this.openedBy === 'hover') {
      this.openedBy = 'click'; // a click after hovering keeps it open
      return;
    }
    if (this.open()) this.close();
    else this.show('click');
  }

  protected onTriggerKeydown(event: KeyboardEvent): void {
    if (event.key === 'ArrowDown') {
      event.preventDefault();
      this.show('click');
      // Focus only after the open menu is rendered (a hidden link cannot take focus).
      afterNextRender(() => this.links()[0]?.focus(), { injector: this.injector });
    }
  }

  protected onMenuKeydown(event: KeyboardEvent): void {
    const links = this.links();
    const i = links.indexOf(document.activeElement as HTMLAnchorElement);
    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      event.preventDefault();
      const next =
        event.key === 'ArrowDown' ? (i + 1) % links.length : (i - 1 + links.length) % links.length;
      links[next]?.focus();
    }
  }

  protected choose(): void {
    this.close();
    this.navigated.emit();
  }

  protected onPointerEnter(): void {
    if (!this.canHover || this.isMobileLayout()) return;
    clearTimeout(this.leaveTimer);
    if (!this.open()) this.show('hover');
  }

  protected onPointerLeave(): void {
    if (!this.canHover || this.openedBy !== 'hover') return;
    this.leaveTimer = setTimeout(() => this.close(), 180);
  }

  /** Closes when focus leaves the dropdown (checked after focus settles, not via relatedTarget). */
  protected onFocusOut(): void {
    setTimeout(() => {
      if (!this.host.nativeElement.contains(document.activeElement)) this.close();
    });
  }

  protected closeAndFocus(event: Event): void {
    if (!this.open()) return;
    event.stopPropagation(); // don't also close the whole mobile menu
    this.close();
    this.trigger().nativeElement.focus();
  }

  private show(by: 'hover' | 'click'): void {
    this.openedBy = by;
    this.open.set(true);
  }

  private close(): void {
    clearTimeout(this.leaveTimer);
    this.openedBy = null;
    this.open.set(false);
  }

  private links(): HTMLAnchorElement[] {
    return Array.from(
      this.host.nativeElement.querySelectorAll<HTMLAnchorElement>('.dropdown__link'),
    );
  }

  private isMobileLayout(): boolean {
    return typeof matchMedia === 'function' && matchMedia('(max-width: 900px)').matches;
  }
}
